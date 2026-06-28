from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

ADVISORY_ODDS_MATH_MODE = "ADVISORY_ONLY"

PLAYABLE_PLUS_EV = "PLAYABLE_PLUS_EV"
WATCHLIST_VALUE = "WATCHLIST_VALUE"
PREDICTION_ONLY_NOT_PLUS_EV = "PREDICTION_ONLY_NOT_PLUS_EV"
BLOCKED_NEGATIVE_EV = "BLOCKED_NEGATIVE_EV"
BLOCKED_STALE_LINE = "BLOCKED_STALE_LINE"
BLOCKED_DUPLICATE_CONFLICT = "BLOCKED_DUPLICATE_CONFLICT"
BLOCKED_INCOMPLETE_MARKET = "BLOCKED_INCOMPLETE_MARKET"
BLOCKED_MISSING_ODDS = "BLOCKED_MISSING_ODDS"
BLOCKED_LOW_MODEL_CONFIDENCE = "BLOCKED_LOW_MODEL_CONFIDENCE"
BLOCKED_WEAK_SHADOW_SAMPLE = "BLOCKED_WEAK_SHADOW_SAMPLE"
BLOCKED_INVALID_PROBABILITY = "BLOCKED_INVALID_PROBABILITY"

ADVISORY_COLUMNS = [
    "advisory_raw_implied_probability",
    "advisory_no_vig_implied_probability",
    "advisory_market_hold",
    "advisory_market_hold_pct",
    "advisory_raw_edge",
    "advisory_no_vig_edge",
    "advisory_raw_EV",
    "advisory_best_price_EV",
    "advisory_no_vig_value_ratio",
    "advisory_fair_odds",
    "advisory_target_odds",
    "advisory_current_decimal_odds",
    "advisory_best_available_decimal_odds",
    "advisory_best_available_sportsbook",
    "advisory_line_shopping_gain",
    "advisory_line_shopping_gain_pct",
    "advisory_best_price_no_vig_edge",
    "advisory_stale_line_status",
    "advisory_stale_line_reason",
    "advisory_market_completeness_status",
    "advisory_duplicate_event_status",
    "advisory_duplicate_event_reason",
    "advisory_conflict_status",
    "advisory_conflict_reason",
    "advisory_playable_status",
    "advisory_playable_reason",
    "advisory_prediction_only_reason",
    "advisory_odds_value_tier",
    "advisory_odds_math_mode",
]

DEFAULT_CONFIG: dict[str, Any] = {
    "minimum_playable_raw_EV": 0.01,
    "minimum_playable_no_vig_edge": 0.015,
    "minimum_playable_model_probability": 0.52,
    "maximum_market_hold": 0.12,
    "stale_line_minutes": 20,
    "minimum_line_shopping_gain_pct_for_upgrade": 0.005,
    "weak_shadow_sample_can_only_watchlist": True,
    "allow_playable_without_shadow_model": False,
    "target_decimal_margin": 0.03,
    "strict_unknown_stale_line_block": False,
    "strict_stale_line_block": True,
    "allow_multiple_markets": False,
}

ODDS_FIELDS = ("decimal_odds", "decimal_price", "price_decimal", "odds_decimal", "odds", "price")
AMERICAN_ODDS_FIELDS = ("american_odds", "american_price", "price_american")
PROBABILITY_FIELDS = ("model_probability", "model_probability_clean", "final_probability", "probability", "confidence_probability")
SPORTSBOOK_FIELDS = ("sportsbook", "bookmaker", "book", "odds_source")
EVENT_FIELDS = ("event_id", "game_id", "matchup", "event", "event_name", "game")
MARKET_FIELDS = ("market_type", "market", "bet_type")
SELECTION_FIELDS = ("selection", "prediction", "pick", "public_pick", "outcome", "name", "team")
LINE_FIELDS = ("line", "point", "points", "spread", "handicap", "total", "total_points")
ODDS_TIMESTAMP_FIELDS = ("odds_timestamp", "odds_last_update", "last_update", "pulled_at_utc", "created_at_utc")
EVENT_TIMESTAMP_FIELDS = ("event_start_time", "event_start_utc", "commence_time")
RESULT_FIELDS = ("result", "grade", "outcome_result", "official_result", "final_result", "result_status", "pick_result", "settled_status")
HISTORICAL_TOKENS = {"win", "won", "w", "loss", "lost", "l", "push", "void", "cancel", "cancelled", "canceled", "graded"}
DRAW_TOKENS = {"draw", "tie", "x"}
OVER_TOKENS = {"over", "o"}
UNDER_TOKENS = {"under", "u"}
WEAK_SHADOW_LABELS = {"", "DATA BLOCKED", "WEAK SAMPLE", "NEEDS MORE DATA", "USABLE SAMPLE"}


def _cfg(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    out = dict(DEFAULT_CONFIG)
    out.update(dict(config or {}))
    return out


def _first_value(row: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        value = row.get(name)
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() not in {"nan", "none", "null"}:
            return value
    return None


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def _round(value: Any) -> float | None:
    parsed = _to_float(value)
    return None if parsed is None else round(parsed, 6)


def normalize_decimal_odds(row: Mapping[str, Any]) -> float | None:
    for name in ODDS_FIELDS:
        value = _to_float(row.get(name))
        if value is None:
            continue
        if value > 1.0:
            return value
        if value <= -100 or value >= 100:
            return american_to_decimal(value)
    american = _to_float(_first_value(row, AMERICAN_ODDS_FIELDS))
    if american is not None:
        return american_to_decimal(american)
    return None


def american_to_decimal(american_odds: float | int | None) -> float | None:
    value = _to_float(american_odds)
    if value is None or value == 0:
        return None
    if value > 0:
        return 1.0 + value / 100.0
    return 1.0 + 100.0 / abs(value)


def normalize_model_probability(row: Mapping[str, Any]) -> float | None:
    value = _to_float(_first_value(row, PROBABILITY_FIELDS))
    if value is None:
        return None
    if value > 1.0 and value <= 100.0:
        value = value / 100.0
    if value <= 0.0 or value > 1.0:
        return None
    return value


def _norm_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    return " ".join(text.replace("–", "-").replace("—", "-").split())


def _first_text(row: Mapping[str, Any], names: Sequence[str]) -> str:
    value = _first_value(row, names)
    return str(value).strip() if value is not None else ""


def sportsbook_identity(row: Mapping[str, Any]) -> str:
    return _norm_text(_first_text(row, SPORTSBOOK_FIELDS)) or "unknown_sportsbook"


def event_identity(row: Mapping[str, Any]) -> str:
    direct = _first_text(row, EVENT_FIELDS)
    if direct:
        return _norm_text(direct)
    home = _first_text(row, ("home_team", "home"))
    away = _first_text(row, ("away_team", "away"))
    if home or away:
        return _norm_text(f"{away} at {home}")
    teams = _first_text(row, ("teams",))
    sport = _first_text(row, ("sport",))
    league = _first_text(row, ("league",))
    start = _first_text(row, EVENT_TIMESTAMP_FIELDS)
    return _norm_text("|".join([sport, league, teams, start])) or "unknown_event"


def market_identity(row: Mapping[str, Any]) -> str:
    return _norm_text(_first_text(row, MARKET_FIELDS)) or "unknown_market"


def selection_identity(row: Mapping[str, Any]) -> str:
    return _norm_text(_first_text(row, SELECTION_FIELDS)) or "unknown_selection"


def line_identity(row: Mapping[str, Any]) -> str:
    value = _first_value(row, LINE_FIELDS)
    return _norm_text(value) if value is not None else ""


def _is_total_market(market: str) -> bool:
    return any(token in market for token in ("total", "over_under", "over/under", "ou"))


def _is_spread_market(market: str) -> bool:
    return any(token in market for token in ("spread", "handicap", "run line", "puck line"))


def _is_h2h_market(market: str) -> bool:
    return any(token in market for token in ("h2h", "moneyline", "money line", "ml", "winner"))


def _is_soccer_three_way(row: Mapping[str, Any], market: str, selections: set[str]) -> bool:
    sport = _norm_text(_first_text(row, ("sport",)))
    if any(token in market for token in ("1x2", "3way", "3-way", "three way", "three-way")):
        return True
    return sport in {"soccer", "football"} and _is_h2h_market(market) and bool(selections & DRAW_TOKENS)


def _market_group_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    market = market_identity(row)
    line = line_identity(row) if _is_spread_market(market) or _is_total_market(market) else ""
    return (event_identity(row), market, sportsbook_identity(row), line)


def _selection_group_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    market = market_identity(row)
    line = line_identity(row) if _is_spread_market(market) or _is_total_market(market) else ""
    return (event_identity(row), market, selection_identity(row), line)


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    numeric = _to_float(value)
    if numeric is not None and str(value).strip().isdigit():
        try:
            return datetime.fromtimestamp(numeric, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _is_historical(row: Mapping[str, Any]) -> bool:
    text = " ".join(_norm_text(row.get(field)) for field in RESULT_FIELDS)
    tokens = set(text.replace("/", " ").replace(";", " ").replace(",", " ").split())
    if tokens & HISTORICAL_TOKENS:
        return True
    if row.get("proof_status") and _norm_text(row.get("proof_status")) in {"resolved", "graded", "final"}:
        return True
    return False


def _odds_timestamp(row: Mapping[str, Any]) -> datetime | None:
    for name in ODDS_TIMESTAMP_FIELDS:
        parsed = parse_datetime(row.get(name))
        if parsed is not None:
            return parsed.astimezone(timezone.utc)
    return None


def _event_timestamp(row: Mapping[str, Any]) -> datetime | None:
    for name in EVENT_TIMESTAMP_FIELDS:
        parsed = parse_datetime(row.get(name))
        if parsed is not None:
            return parsed.astimezone(timezone.utc)
    return None


def stale_line_status(row: Mapping[str, Any], *, now: datetime | None = None, config: Mapping[str, Any] | None = None) -> tuple[str, str]:
    cfg = _cfg(config)
    current = (now or cfg.get("now_utc") or datetime.now(timezone.utc))
    if not isinstance(current, datetime):
        current = datetime.now(timezone.utc)
    current = current if current.tzinfo else current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    if _is_historical(row):
        return "HISTORICAL_ROW", "row_has_historical_or_graded_result"
    event_time = _event_timestamp(row)
    if event_time is not None and event_time <= current:
        return "EVENT_STARTED", "event_start_time_is_not_future"
    odds_time = _odds_timestamp(row)
    if odds_time is None:
        return "UNKNOWN", "missing_odds_freshness_timestamp"
    age_seconds = (current - odds_time).total_seconds()
    if age_seconds > float(cfg["stale_line_minutes"]) * 60.0:
        return "STALE", "odds_timestamp_older_than_threshold"
    return "FRESH", "odds_timestamp_within_threshold"


def _market_completeness(rows: Sequence[Mapping[str, Any]]) -> tuple[str, float | None]:
    valid_rows = [row for row in rows if row.get("_advisory_raw_implied_probability") is not None]
    if not valid_rows:
        return "INCOMPLETE_MARKET", None
    first = valid_rows[0]
    market = market_identity(first)
    selections = {selection_identity(row) for row in valid_rows if selection_identity(row) != "unknown_selection"}
    total_raw = sum(float(row["_advisory_raw_implied_probability"]) for row in valid_rows)
    if total_raw <= 0:
        return "INCOMPLETE_MARKET", None
    if "future" in market or "outright" in market:
        return "INCOMPLETE_MARKET", None
    if _is_total_market(market):
        has_over = any(sel.split()[0:1] and sel.split()[0] in OVER_TOKENS for sel in selections) or bool(selections & OVER_TOKENS)
        has_under = any(sel.split()[0:1] and sel.split()[0] in UNDER_TOKENS for sel in selections) or bool(selections & UNDER_TOKENS)
        return ("COMPLETE_MARKET", total_raw) if has_over and has_under else ("INCOMPLETE_MARKET", None)
    if _is_spread_market(market):
        return ("COMPLETE_MARKET", total_raw) if len(selections) >= 2 else ("INCOMPLETE_MARKET", None)
    if _is_soccer_three_way(first, market, selections):
        return ("COMPLETE_MARKET", total_raw) if len(selections) >= 3 and bool(selections & DRAW_TOKENS) else ("INCOMPLETE_MARKET", None)
    if _is_h2h_market(market):
        return ("COMPLETE_MARKET", total_raw) if len(selections) >= 2 else ("INCOMPLETE_MARKET", None)
    return "INCOMPLETE_MARKET", None


def _shadow_supported(row: Mapping[str, Any]) -> bool:
    loaded = bool(row.get("lr_model_loaded"))
    quality = str(row.get("model_quality_label") or row.get("baseline_confidence") or "DATA BLOCKED").strip().upper()
    return loaded and quality not in WEAK_SHADOW_LABELS


def _favorable_watchlist(row: Mapping[str, Any], cfg: Mapping[str, Any]) -> bool:
    raw_ev = row.get("advisory_raw_EV")
    best_ev = row.get("advisory_best_price_EV")
    no_vig_edge = row.get("advisory_no_vig_edge")
    if raw_ev is None or float(raw_ev) <= float(cfg["minimum_playable_raw_EV"]):
        return False
    if best_ev is not None and float(best_ev) <= 0:
        return False
    if no_vig_edge is not None and float(no_vig_edge) < 0:
        return False
    return True


def _initial_playable_status(row: Mapping[str, Any], cfg: Mapping[str, Any]) -> tuple[str, str, str]:
    prob = row.get("_model_probability")
    odds = row.get("advisory_current_decimal_odds")
    if odds is None:
        return BLOCKED_MISSING_ODDS, "missing_or_invalid_decimal_odds", ""
    if prob is None:
        return BLOCKED_INVALID_PROBABILITY, "missing_or_invalid_model_probability", ""
    if float(prob) < float(cfg["minimum_playable_model_probability"]):
        return BLOCKED_LOW_MODEL_CONFIDENCE, "model_probability_below_playable_threshold", ""
    stale = row.get("advisory_stale_line_status")
    if stale in {"EVENT_STARTED", "HISTORICAL_ROW"}:
        return BLOCKED_STALE_LINE, str(row.get("advisory_stale_line_reason") or "not_pre_event_fresh_odds"), ""
    if stale == "STALE" and bool(cfg.get("strict_stale_line_block", True)):
        return BLOCKED_STALE_LINE, str(row.get("advisory_stale_line_reason") or "stale_odds"), ""
    if stale == "UNKNOWN" and bool(cfg.get("strict_unknown_stale_line_block", False)):
        return BLOCKED_STALE_LINE, "unknown_odds_freshness_blocked_by_strict_mode", ""
    raw_ev = row.get("advisory_raw_EV")
    if raw_ev is None or float(raw_ev) <= 0:
        return PREDICTION_ONLY_NOT_PLUS_EV, "High-confidence prediction, but current price does not show playable positive EV.", "High-confidence prediction, but current price does not show playable positive EV."
    if float(raw_ev) < float(cfg["minimum_playable_raw_EV"]):
        return WATCHLIST_VALUE, "positive_EV_below_playable_threshold", ""
    market_hold = row.get("advisory_market_hold")
    if market_hold is not None and float(market_hold) > float(cfg["maximum_market_hold"]):
        return WATCHLIST_VALUE, "market_hold_above_threshold", ""
    completeness = row.get("advisory_market_completeness_status")
    no_vig_edge = row.get("advisory_no_vig_edge")
    if completeness != "COMPLETE_MARKET" or no_vig_edge is None:
        return WATCHLIST_VALUE, "positive_raw_EV_but_no_complete_no_vig_market", ""
    if float(no_vig_edge) < float(cfg["minimum_playable_no_vig_edge"]):
        return PREDICTION_ONLY_NOT_PLUS_EV, "High-confidence prediction, but current price does not show playable positive EV.", "High-confidence prediction, but current price does not show playable positive EV."
    best_ev = row.get("advisory_best_price_EV")
    if best_ev is not None and float(best_ev) <= 0:
        return WATCHLIST_VALUE, "best_available_price_EV_not_positive", ""
    shadow_ok = _shadow_supported(row)
    if not shadow_ok and not bool(cfg.get("allow_playable_without_shadow_model", False)):
        return WATCHLIST_VALUE, "shadow_model_missing_or_data_blocked_watchlist_only", ""
    if not shadow_ok and bool(cfg.get("allow_playable_without_shadow_model", False)):
        if float(no_vig_edge) < 0.03:
            return WATCHLIST_VALUE, "conservative_fallback_no_vig_edge_below_3pct", ""
        if best_ev is None or float(best_ev) < 0.03:
            return WATCHLIST_VALUE, "conservative_fallback_best_price_EV_below_3pct", ""
        if stale != "FRESH":
            return WATCHLIST_VALUE, "conservative_fallback_requires_fresh_odds", ""
    return PLAYABLE_PLUS_EV, "positive_EV_no_vig_edge_and_safety_checks_passed", ""


def _rank_value(row: Mapping[str, Any]) -> tuple[float, float, float, float, float, float, float]:
    status_score = 1.0 if row.get("advisory_playable_status") == PLAYABLE_PLUS_EV else 0.0
    freshness = 1.0 if row.get("advisory_stale_line_status") == "FRESH" else 0.5 if row.get("advisory_stale_line_status") == "UNKNOWN" else 0.0
    return (
        status_score,
        float(row.get("advisory_best_price_EV") or -999.0),
        float(row.get("advisory_no_vig_edge") or -999.0),
        float(row.get("advisory_raw_EV") or -999.0),
        float(row.get("advisory_line_shopping_gain_pct") or 0.0),
        float(row.get("_model_probability") or 0.0),
        freshness,
    )


def build_advisory_odds_value_rows(
    rows: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return proof-safe advisory odds-value rows without mutating inputs."""

    cfg = _cfg(config)
    source_rows = [deepcopy(dict(row)) for row in rows or [] if isinstance(row, Mapping)]
    prepared: list[dict[str, Any]] = []
    for idx, row in enumerate(source_rows):
        out = deepcopy(row)
        decimal_odds = normalize_decimal_odds(out)
        probability = normalize_model_probability(out)
        raw_implied = 1.0 / decimal_odds if decimal_odds and decimal_odds > 1 else None
        fair_odds = 1.0 / probability if probability else None
        target_odds = fair_odds + float(cfg["target_decimal_margin"]) if fair_odds else None
        stale_status, stale_reason = stale_line_status(out, now=now, config=cfg)
        out.update({
            "_advisory_index": idx,
            "_model_probability": probability,
            "_event_identity": event_identity(out),
            "_market_identity": market_identity(out),
            "_selection_identity": selection_identity(out),
            "_sportsbook_identity": sportsbook_identity(out),
            "_advisory_raw_implied_probability": raw_implied,
            "advisory_raw_implied_probability": _round(raw_implied),
            "advisory_no_vig_implied_probability": None,
            "advisory_market_hold": None,
            "advisory_market_hold_pct": None,
            "advisory_raw_edge": _round(probability - raw_implied) if probability is not None and raw_implied is not None else None,
            "advisory_no_vig_edge": None,
            "advisory_raw_EV": _round(probability * decimal_odds - 1.0) if probability is not None and decimal_odds is not None else None,
            "advisory_best_price_EV": None,
            "advisory_no_vig_value_ratio": None,
            "advisory_fair_odds": _round(fair_odds),
            "advisory_target_odds": _round(target_odds),
            "advisory_current_decimal_odds": _round(decimal_odds),
            "advisory_best_available_decimal_odds": _round(decimal_odds),
            "advisory_best_available_sportsbook": _first_text(out, SPORTSBOOK_FIELDS),
            "advisory_line_shopping_gain": 0.0 if decimal_odds is not None else None,
            "advisory_line_shopping_gain_pct": 0.0 if decimal_odds is not None else None,
            "advisory_best_price_no_vig_edge": None,
            "advisory_stale_line_status": stale_status,
            "advisory_stale_line_reason": stale_reason,
            "advisory_market_completeness_status": "INCOMPLETE_MARKET",
            "advisory_duplicate_event_status": "UNIQUE_EVENT",
            "advisory_duplicate_event_reason": "single_row_for_event",
            "advisory_conflict_status": "NO_CONFLICT",
            "advisory_conflict_reason": "none",
            "advisory_prediction_only_reason": "",
            "advisory_odds_value_tier": "UNRATED",
            "advisory_odds_math_mode": ADVISORY_ODDS_MATH_MODE,
        })
        prepared.append(out)

    market_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    selection_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    event_groups: dict[str, list[dict[str, Any]]] = {}
    for row in prepared:
        market_groups.setdefault(_market_group_key(row), []).append(row)
        selection_groups.setdefault(_selection_group_key(row), []).append(row)
        event_groups.setdefault(str(row["_event_identity"]), []).append(row)

    no_vig_by_index: dict[int, float | None] = {}
    for group in market_groups.values():
        completeness, total_raw = _market_completeness(group)
        hold = total_raw - 1.0 if total_raw is not None else None
        for row in group:
            row["advisory_market_completeness_status"] = completeness
            row["advisory_market_hold"] = _round(hold)
            row["advisory_market_hold_pct"] = _round(hold * 100.0) if hold is not None else None
            raw = row.get("_advisory_raw_implied_probability")
            if completeness == "COMPLETE_MARKET" and total_raw and raw is not None:
                no_vig = float(raw) / float(total_raw)
                no_vig_by_index[int(row["_advisory_index"])] = no_vig
                row["advisory_no_vig_implied_probability"] = _round(no_vig)
                probability = row.get("_model_probability")
                if probability is not None:
                    row["advisory_no_vig_edge"] = _round(float(probability) - no_vig)
                    row["advisory_no_vig_value_ratio"] = _round(float(probability) / no_vig - 1.0) if no_vig > 0 else None

    for group in selection_groups.values():
        valid = [row for row in group if row.get("advisory_current_decimal_odds") is not None]
        if not valid:
            continue
        best = sorted(valid, key=lambda item: (-float(item.get("advisory_current_decimal_odds") or 0), str(item.get("advisory_best_available_sportsbook") or ""), int(item.get("_advisory_index") or 0)))[0]
        best_odds = float(best.get("advisory_current_decimal_odds") or 0)
        best_book = _first_text(best, SPORTSBOOK_FIELDS)
        best_no_vig = no_vig_by_index.get(int(best["_advisory_index"]))
        for row in group:
            current = row.get("advisory_current_decimal_odds")
            row["advisory_best_available_decimal_odds"] = _round(best_odds)
            row["advisory_best_available_sportsbook"] = best_book
            if current is not None and float(current) > 0:
                gain = best_odds - float(current)
                row["advisory_line_shopping_gain"] = _round(gain)
                row["advisory_line_shopping_gain_pct"] = _round(gain / float(current))
            probability = row.get("_model_probability")
            if probability is not None:
                row["advisory_best_price_EV"] = _round(float(probability) * best_odds - 1.0)
                row["advisory_best_price_no_vig_edge"] = _round(float(probability) - best_no_vig) if best_no_vig is not None else None

    for event, group in event_groups.items():
        if len(group) > 1:
            seen_selection_keys: dict[tuple[str, str, str], int] = {}
            for row in group:
                row["advisory_duplicate_event_status"] = "MULTIPLE_ROWS_SAME_EVENT"
                row["advisory_duplicate_event_reason"] = "multiple_rows_share_event_identity"
                key = (str(row.get("_market_identity")), str(row.get("_selection_identity")), str(row.get("_sportsbook_identity")))
                seen_selection_keys[key] = seen_selection_keys.get(key, 0) + 1
            markets: dict[str, set[str]] = {}
            for row in group:
                markets.setdefault(str(row.get("_market_identity")), set()).add(str(row.get("_selection_identity")))
            conflict = any(len(selections) > 1 for selections in markets.values())
            if conflict:
                for row in group:
                    row["advisory_conflict_status"] = "CONFLICTING_MARKET_SIDES"
                    row["advisory_conflict_reason"] = "multiple_sides_or_correlated_picks_in_same_event"
            for row in group:
                key = (str(row.get("_market_identity")), str(row.get("_selection_identity")), str(row.get("_sportsbook_identity")))
                if seen_selection_keys.get(key, 0) > 1:
                    row["advisory_duplicate_event_status"] = "EXACT_DUPLICATE"
                    row["advisory_duplicate_event_reason"] = "same_event_market_selection_and_sportsbook_repeated"

    for row in prepared:
        status, reason, prediction_only = _initial_playable_status(row, cfg)
        row["advisory_playable_status"] = status
        row["advisory_playable_reason"] = reason
        row["advisory_prediction_only_reason"] = prediction_only
        if status == PLAYABLE_PLUS_EV:
            row["advisory_odds_value_tier"] = "PLAYABLE"
        elif status == WATCHLIST_VALUE:
            row["advisory_odds_value_tier"] = "WATCHLIST"
        elif status == PREDICTION_ONLY_NOT_PLUS_EV:
            row["advisory_odds_value_tier"] = "PREDICTION_ONLY"
        else:
            row["advisory_odds_value_tier"] = "BLOCKED"

    if not bool(cfg.get("allow_multiple_markets", False)):
        for group in event_groups.values():
            playable = [row for row in group if row.get("advisory_playable_status") == PLAYABLE_PLUS_EV]
            if len(playable) <= 1:
                continue
            best = max(playable, key=_rank_value)
            for row in playable:
                if row is best:
                    continue
                row["advisory_playable_status"] = BLOCKED_DUPLICATE_CONFLICT
                row["advisory_playable_reason"] = "stronger_advisory_playable_pick_exists_for_same_event"
                row["advisory_odds_value_tier"] = "BLOCKED"
                row["advisory_conflict_status"] = "BLOCKED_DUPLICATE_CONFLICT"
                row["advisory_conflict_reason"] = "only_one_strongest_advisory_playable_pick_allowed_per_event"

    cleaned: list[dict[str, Any]] = []
    for row in prepared:
        cleaned_row = {key: value for key, value in row.items() if not str(key).startswith("_")}
        cleaned.append(cleaned_row)
    return cleaned


def advisory_odds_value_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    data = [dict(row) for row in rows or [] if isinstance(row, Mapping)]
    statuses: dict[str, int] = {}
    stale: dict[str, int] = {}
    completeness: dict[str, int] = {}
    conflicts = 0
    for row in data:
        statuses[str(row.get("advisory_playable_status") or "UNKNOWN")] = statuses.get(str(row.get("advisory_playable_status") or "UNKNOWN"), 0) + 1
        stale[str(row.get("advisory_stale_line_status") or "UNKNOWN")] = stale.get(str(row.get("advisory_stale_line_status") or "UNKNOWN"), 0) + 1
        completeness[str(row.get("advisory_market_completeness_status") or "UNKNOWN")] = completeness.get(str(row.get("advisory_market_completeness_status") or "UNKNOWN"), 0) + 1
        if str(row.get("advisory_conflict_status") or "NO_CONFLICT") != "NO_CONFLICT":
            conflicts += 1
    return {
        "advisory_odds_math_mode": ADVISORY_ODDS_MATH_MODE,
        "rows": len(data),
        "playable_plus_ev": statuses.get(PLAYABLE_PLUS_EV, 0),
        "watchlist_value": statuses.get(WATCHLIST_VALUE, 0),
        "prediction_only_not_plus_ev": statuses.get(PREDICTION_ONLY_NOT_PLUS_EV, 0),
        "blocked_rows": sum(count for status, count in statuses.items() if status.startswith("BLOCKED")),
        "fresh_rows": stale.get("FRESH", 0),
        "stale_rows": stale.get("STALE", 0),
        "unknown_freshness_rows": stale.get("UNKNOWN", 0),
        "complete_markets": completeness.get("COMPLETE_MARKET", 0),
        "incomplete_markets": completeness.get("INCOMPLETE_MARKET", 0),
        "conflict_rows": conflicts,
        "live_application": "OFF",
        "applied_live_count": 0,
        "proof_history_mutation": "FORBIDDEN",
    }
