"""Subscriber-ready bet catalog and betting magazine helpers.

The helpers rank already-supplied analysis and odds rows. They do not fetch odds,
place bets, guarantee winners, or claim a guaranteed 65% actual win rate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

CORE_PROBABILITY_THRESHOLD = 0.65
DOUBLE_MONEY_DECIMAL = 2.0
FINAL_DECISIONS = {
    "BET", "SMALL BET", "CHAIN ONLY", "WAIT FOR BETTER ODDS", "WATCH ONLY",
    "NO BET", "GOOD READ, BAD PRICE", "BAD VALUE", "AGGRESSIVE ONLY",
}
CATALOG_SECTIONS = (
    "Best 65%+ Singles", "Best Good-Odds Bets", "Closest Double-Money Bets",
    "Conservative Baseball Chains", "Balanced Baseball Chains", "Aggressive Baseball Chains",
    "Player Prop Catalog", "Home Run Watchlist", "Good Read / Bad Price", "No-Bet List",
)
_CHAIN_MARKERS = {"chain", "parlay", "same game parlay", "sgp"}
_PROP_MARKERS = {"player", "prop", "hits", "total bases", "rbi", "runs", "strikeouts", "outs"}
_HR_MARKERS = {"home run", "hr", "homer"}


def _text(row: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _num(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _prob(row: Mapping[str, Any], *keys: str) -> float | None:
    value = _num(row, *keys)
    if value is None:
        return None
    if value > 1:
        value /= 100.0
    return max(0.0, min(1.0, value))


def american_to_decimal(american_odds: float) -> float | None:
    if american_odds == 0:
        return None
    return 1 + american_odds / 100 if american_odds > 0 else 1 + 100 / abs(american_odds)


def decimal_to_american(decimal_odds: float | None) -> int | None:
    if decimal_odds is None or decimal_odds <= 1:
        return None
    return int(round((decimal_odds - 1) * 100)) if decimal_odds >= 2 else int(round(-100 / (decimal_odds - 1)))


def normalize_decimal_odds(row: Mapping[str, Any]) -> float | None:
    decimal = _num(row, "decimal_odds", "decimal_price", "current_decimal_odds", "odds_at_pick")
    if decimal and decimal > 1:
        return decimal
    american = _num(row, "american_odds", "current_american_odds", "odds")
    return american_to_decimal(american) if american is not None else None


def implied_probability_from_decimal(decimal_odds: float | None) -> float | None:
    return None if decimal_odds is None or decimal_odds <= 1 else 1 / decimal_odds


def fmt_prob(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.1%}"


def fmt_dec(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.2f}"


def fmt_american(decimal_odds: float | None) -> str:
    american = decimal_to_american(decimal_odds)
    if american is None:
        return "N/A"
    return f"+{american}" if american > 0 else str(american)


def risk_level(score: float | None) -> str:
    if score is None:
        return "unknown"
    return "low" if score <= 3 else "medium" if score <= 6 else "high" if score <= 8 else "very high"


def _market_text(row: Mapping[str, Any]) -> str:
    return " ".join(_text(row, key).lower() for key in ("bet_type", "market", "market_type", "exact_bet", "pick", "selection"))


def is_chain(row: Mapping[str, Any]) -> bool:
    market = _market_text(row)
    return any(marker in market for marker in _CHAIN_MARKERS) or bool(row.get("legs"))


def is_home_run_prop(row: Mapping[str, Any]) -> bool:
    return any(marker in _market_text(row) for marker in _HR_MARKERS)


def is_player_prop(row: Mapping[str, Any]) -> bool:
    market = _market_text(row)
    return is_home_run_prop(row) or any(marker in market for marker in _PROP_MARKERS)


def _model_probability(row: Mapping[str, Any]) -> float | None:
    return _prob(row, "model_probability", "learned_model_probability", "probability", "projected_probability")


def _chain_probability(row: Mapping[str, Any]) -> float | None:
    supplied = _prob(row, "combined_adjusted_probability", "adjusted_combined_probability", "chain_probability")
    if supplied is not None:
        return supplied
    legs = row.get("legs")
    if not isinstance(legs, Sequence) or isinstance(legs, (str, bytes)) or not legs:
        return None
    combined = 1.0
    for leg in legs:
        if not isinstance(leg, Mapping):
            return None
        probability = _model_probability(leg)
        if probability is None:
            return None
        combined *= probability
    penalty = _num(row, "correlation_penalty")
    if penalty is None:
        penalty = 0.03 * max(len(legs) - 1, 0)
    return max(0.0, combined * (1.0 - penalty))


def _edge(model_probability: float | None, implied_probability: float | None, supplied: float | None) -> float | None:
    if supplied is not None:
        return supplied / 100 if abs(supplied) > 1 else supplied
    if model_probability is None or implied_probability is None:
        return None
    return model_probability - implied_probability


def _ev(model_probability: float | None, decimal_odds: float | None, supplied: float | None) -> float | None:
    if supplied is not None:
        return supplied
    if model_probability is None or decimal_odds is None:
        return None
    return model_probability * decimal_odds - 1


def _analysis_pass(row: Mapping[str, Any]) -> bool:
    gate = _text(row, "sports_analysis_gate", "analysis_gate").lower()
    if gate in {"pass", "passed", "true", "yes", "supported"}:
        return True
    if gate in {"fail", "failed", "false", "no", "unsupported"}:
        return False
    return bool(_text(row, "why_pick", "why_we_are_picking", "analysis_summary", "reason", "explanation") or _num(row, "analysis_confidence", "pattern_points") is not None)


def _risk_score(row: Mapping[str, Any], model_probability: float | None, ev: float | None) -> float | None:
    supplied = _num(row, "risk_score", "blended_risk_score")
    if supplied is not None:
        return max(1.0, min(10.0, supplied))
    if model_probability is None:
        return None
    score = 10 - model_probability * 10
    if ev and ev > 0:
        score -= min(ev * 4, 1.5)
    if is_chain(row):
        legs = row.get("legs")
        score += len(legs) * 0.65 if isinstance(legs, Sequence) and not isinstance(legs, (str, bytes)) else 1.5
    if is_player_prop(row):
        score += 0.8
    if is_home_run_prop(row):
        score += 1.7
    return round(max(1.0, min(10.0, score)), 1)


def _stake(row: Mapping[str, Any], score: float | None) -> str:
    supplied = _text(row, "recommended_stake", "stake_suggestion", "stake")
    if supplied:
        return supplied
    if score is None:
        return "Review manually"
    return "1.0 unit max" if score <= 3 else "0.5 unit max" if score <= 6 else "0.25 unit max / small bet only" if score <= 8 else "Watch only unless aggressive"


def _decision(row: Mapping[str, Any], analysis_ok: bool, odds_ok: bool, probability: float | None, ev: float | None, score: float | None) -> str:
    supplied = _text(row, "final_decision", "recommendation", "decision").upper()
    if supplied in FINAL_DECISIONS:
        return supplied
    if not analysis_ok:
        return "WATCH ONLY"
    if not odds_ok:
        return "GOOD READ, BAD PRICE" if probability and probability >= CORE_PROBABILITY_THRESHOLD else "BAD VALUE"
    if is_chain(row):
        return "AGGRESSIVE ONLY" if score and score > 8 else "SMALL BET"
    if is_home_run_prop(row):
        return "SMALL BET" if ev and ev > 0 and probability and probability >= CORE_PROBABILITY_THRESHOLD else "AGGRESSIVE ONLY"
    if probability is None or probability < CORE_PROBABILITY_THRESHOLD:
        return "WATCH ONLY"
    if score and score > 8:
        return "AGGRESSIVE ONLY"
    return "SMALL BET" if score and score > 6 else "BET"


def _why_pick(row: Mapping[str, Any], probability: float | None, implied: float | None, edge: float | None, score: float | None) -> str:
    supplied = _text(row, "why_pick", "why_we_are_picking", "analysis_summary", "reason", "explanation")
    if supplied:
        return supplied
    game = _text(row, "game", "event", "event_name", "matchup", default="the game")
    parts = [f"The available model fields support {game} at {fmt_prob(probability)} projected probability."]
    if implied is not None and edge is not None:
        parts.append(f"The market implies {fmt_prob(implied)}, creating a {edge:.1%} model-market edge.")
    if score is not None:
        parts.append(f"The blended risk score is {score:.1f}/10, which is {risk_level(score)} risk.")
    return " ".join(parts)


def _why_lose(row: Mapping[str, Any]) -> str:
    supplied = _text(row, "why_lose", "why_it_could_lose", "risk_reason", "hidden_risk")
    if supplied:
        return supplied
    if is_home_run_prop(row):
        return "Home run props are high-variance markets and can lose even when the matchup profile is favorable."
    if is_player_prop(row):
        return "Player props can lose from lineup changes, limited plate appearances, pitcher approach, or game script."
    if is_chain(row):
        return "A chain bet can lose if any leg fails, and combined probability drops as legs are added."
    return "The bet can lose from late lineup changes, pitcher variance, bullpen failure, market movement, or normal sports variance."


@dataclass(frozen=True)
class CatalogPick:
    pick_title: str
    game: str
    sport_league: str
    start_time: str
    bet_type: str
    exact_bet: str
    sportsbook_casino: str
    current_odds: str
    closest_double_money_odds: str
    implied_probability: float | None
    model_probability: float | None
    passes_65_filter: bool
    edge: float | None
    expected_value: float | None
    risk_score: float | None
    risk_level: str
    recommended_stake: str
    why_pick: str
    why_lose: str
    final_decision: str
    minimum_playable_odds: str
    chain_combined_probability: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def build_catalog_pick(row: Mapping[str, Any]) -> CatalogPick:
    decimal = normalize_decimal_odds(row)
    implied = _prob(row, "implied_probability", "market_implied_probability") or implied_probability_from_decimal(decimal)
    probability = _chain_probability(row) if is_chain(row) else _model_probability(row)
    edge = _edge(probability, implied, _num(row, "edge", "model_market_edge"))
    ev = _ev(probability, decimal, _num(row, "expected_value", "ev"))
    score = _risk_score(row, probability, ev)
    odds_ok = (ev is not None and ev > 0) or (edge is not None and edge > 0)
    decision = _decision(row, _analysis_pass(row), odds_ok, probability, ev, score)
    exact_bet = _text(row, "exact_bet", "pick", "prediction", "selection", default="Bet not specified")
    min_odds = None if not probability else 1 / probability
    return CatalogPick(
        pick_title=_text(row, "pick_title", "title") or f"{exact_bet} — {decision}",
        game=_text(row, "game", "event", "event_name", "matchup", default="Game not specified"),
        sport_league=_text(row, "sport_league", "league", "sport", default="MLB Baseball"),
        start_time=_text(row, "start_time", "commence_time", "event_time", default="Not specified"),
        bet_type=_text(row, "bet_type", "market", "market_type", default="Market not specified"),
        exact_bet=exact_bet,
        sportsbook_casino=_text(row, "sportsbook_casino", "bookmaker", "best_bookmaker", "sportsbook", default="Best available"),
        current_odds=f"{fmt_american(decimal)} / {fmt_dec(decimal)} decimal",
        closest_double_money_odds="N/A" if decimal is None else f"{fmt_american(decimal)} / {fmt_dec(decimal)} decimal; gap {abs(decimal - DOUBLE_MONEY_DECIMAL):.2f} from 2.00",
        implied_probability=implied,
        model_probability=probability,
        passes_65_filter=bool(probability is not None and probability >= CORE_PROBABILITY_THRESHOLD),
        edge=edge,
        expected_value=ev,
        risk_score=score,
        risk_level=risk_level(score),
        recommended_stake=_stake(row, score),
        why_pick=_why_pick(row, probability, implied, edge, score),
        why_lose=_why_lose(row),
        final_decision=decision,
        minimum_playable_odds=fmt_dec(min_odds),
        chain_combined_probability=_chain_probability(row) if is_chain(row) else None,
    )


def _sort_key(pick: CatalogPick) -> tuple[int, float, float, float]:
    rank = 0 if pick.final_decision == "BET" else 1 if pick.final_decision == "SMALL BET" else 2
    return (rank, -(pick.expected_value if pick.expected_value is not None else -99), -(pick.model_probability or 0), pick.risk_score or 10)


def build_bet_catalog(rows: Iterable[Mapping[str, Any]]) -> dict[str, list[CatalogPick]]:
    row_list = list(rows)
    sections = {section: [] for section in CATALOG_SECTIONS}
    for row in row_list:
        pick = build_catalog_pick(row)
        playable = pick.final_decision in {"BET", "SMALL BET", "CHAIN ONLY"}
        if pick.passes_65_filter and playable and not is_chain(row) and not is_player_prop(row):
            sections["Best 65%+ Singles"].append(pick)
        if playable and pick.expected_value is not None and pick.expected_value > 0:
            sections["Best Good-Odds Bets"].append(pick)
        decimal = normalize_decimal_odds(row)
        if playable and decimal is not None and abs(decimal - DOUBLE_MONEY_DECIMAL) <= 0.25:
            sections["Closest Double-Money Bets"].append(pick)
        if is_chain(row):
            score = pick.risk_score if pick.risk_score is not None else 10
            sections["Conservative Baseball Chains" if score <= 4 else "Balanced Baseball Chains" if score <= 7 else "Aggressive Baseball Chains"].append(pick)
        if is_player_prop(row) and not is_home_run_prop(row):
            sections["Player Prop Catalog"].append(pick)
        if is_home_run_prop(row):
            sections["Home Run Watchlist"].append(pick)
        if pick.final_decision in {"GOOD READ, BAD PRICE", "WAIT FOR BETTER ODDS"}:
            sections["Good Read / Bad Price"].append(pick)
        if pick.final_decision in {"NO BET", "WATCH ONLY", "BAD VALUE"}:
            sections["No-Bet List"].append(pick)
    for picks in sections.values():
        picks.sort(key=_sort_key)
    return sections


def render_pick_card(pick: CatalogPick) -> str:
    edge = "N/A" if pick.edge is None else f"{pick.edge:.1%}"
    ev = "N/A" if pick.expected_value is None else f"{pick.expected_value:.3f}"
    risk = "N/A" if pick.risk_score is None else f"{pick.risk_score:.1f}/10"
    lines = [
        f"### {pick.pick_title}",
        f"- Game: {pick.game}",
        f"- Sport / League: {pick.sport_league}",
        f"- Start Time: {pick.start_time}",
        f"- Bet Type: {pick.bet_type}",
        f"- Exact Bet: {pick.exact_bet}",
        f"- Sportsbook / Casino: {pick.sportsbook_casino}",
        f"- Current Odds: {pick.current_odds}",
        f"- Closest Double-Money Odds: {pick.closest_double_money_odds}",
        f"- Implied Probability: {fmt_prob(pick.implied_probability)}",
        f"- Model Probability: {fmt_prob(pick.model_probability)}",
        f"- 65%+ Filter: {'PASS' if pick.passes_65_filter else 'FAIL'}",
        f"- Edge: {edge}",
        f"- Expected Value: {ev}",
        f"- Risk Score: {risk}",
        f"- Risk Level: {pick.risk_level}",
        f"- Recommended Stake: {pick.recommended_stake}",
        f"- Minimum Playable Odds: {pick.minimum_playable_odds}",
    ]
    if pick.chain_combined_probability is not None:
        lines.append(f"- Chain Combined Adjusted Probability: {fmt_prob(pick.chain_combined_probability)}")
    lines += [
        f"- Why We Are Picking This Bet: {pick.why_pick}",
        f"- Why This Bet Could Lose: {pick.why_lose}",
        f"- Final Recommendation: {pick.final_decision}",
    ]
    return "\n".join(lines)


def render_betting_magazine(rows: Iterable[Mapping[str, Any]], title: str = "ABA Signal Pro Betting Magazine", subscriber_name: str = "") -> str:
    catalog = build_bet_catalog(rows)
    lines = [f"# {title}", ""]
    if subscriber_name:
        lines += [f"**Subscriber:** {subscriber_name}", ""]
    lines += [
        "**Analytics notice:** This is projected-probability and odds-value analysis only. It does not guarantee wins, profit, or a 65% actual win rate.",
        "Core 65%+ picks use projected model probability. Actual win rate must be tracked separately in the graded ledger.",
        "",
    ]
    for section in CATALOG_SECTIONS:
        lines += [f"## {section}", ""]
        if not catalog[section]:
            lines.append("NO CHAIN RECOMMENDED TODAY" if "Chain" in section else "No qualifying picks in this section.")
            lines.append("")
            continue
        for pick in catalog[section]:
            lines.append(render_pick_card(pick))
            lines.append("")
    return "\n".join(lines).strip() + "\n"
