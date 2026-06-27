from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

BAD_SOURCE_TOKENS = (
    'unavailable', 'missing', 'no odds', 'no_odds', 'api limit', 'limit reached',
    'quota', 'maxed', 'rate limit', 'offline', 'simulated', 'model_only', 'stale',
)
OK_AUDIT_TOKENS = {'', 'pass', 'ok', 'verified', 'live', 'fresh', 'recent', 'nan'}


@dataclass(frozen=True)
class ValueAssessment:
    model_probability: float | None
    decimal_odds: float | None
    raw_implied_probability: float | None
    no_vig_implied_probability: float | None
    edge: float | None
    no_vig_edge: float | None
    expected_value: float | None
    fair_odds: float | None
    target_odds: float | None
    odds_verified: bool
    market_fresh: bool
    color: str
    recommendation: str
    reason: str
    rank_score: float


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(',', '').replace('%', '')
    if not text or text.lower() in {'none', 'null', 'nan', 'n/a', 'na', '--'}:
        return None
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    if parsed != parsed:
        return None
    return parsed


def normalize_probability(value: Any) -> float | None:
    parsed = safe_float(value)
    if parsed is None:
        return None
    parsed = parsed / 100.0 if parsed > 1.0 else parsed
    return parsed if 0.0 <= parsed <= 1.0 else None


def decimal_odds_from(row: Mapping[str, Any]) -> float | None:
    for key in ('decimal_price', 'best_price', 'odds_at_pick', 'odds_decimal', 'average_price', 'avg_price'):
        value = safe_float(row.get(key))
        if value is not None and value > 1.0:
            return value
    return None


def model_probability_from(row: Mapping[str, Any]) -> float | None:
    for key in ('learned_model_probability', 'final_adjusted_probability', 'adjusted_model_probability', 'model_probability_clean', 'model_probability', 'probability', 'final_probability'):
        value = normalize_probability(row.get(key))
        if value is not None and value > 0:
            return value
    return None


def raw_implied_probability(decimal_odds: float | None) -> float | None:
    if decimal_odds is None or decimal_odds <= 1.0:
        return None
    return 1.0 / decimal_odds


def no_vig_probabilities(decimal_odds: Sequence[float]) -> list[float]:
    implied = [raw_implied_probability(odds) for odds in decimal_odds]
    values = [value for value in implied if value is not None and value > 0]
    total = sum(values)
    if total <= 0:
        return [0.0 for _ in decimal_odds]
    return [(value or 0.0) / total for value in implied]


def no_vig_probability_from(row: Mapping[str, Any], raw_implied: float | None) -> float | None:
    for key in ('no_vig_implied_probability', 'market_probability_no_vig', 'market_probability'):
        value = normalize_probability(row.get(key))
        if value is not None and value > 0:
            return value
    overround = safe_float(row.get('market_overround'))
    if raw_implied is not None and overround and overround > 0:
        # Accept either decimal overround (1.04) or margin (0.04).
        denom = overround if overround > 1 else 1.0 + overround
        if denom > 0:
            return max(0.0, min(1.0, raw_implied / denom))
    return raw_implied


def fair_odds(model_probability: float | None) -> float | None:
    if model_probability is None or model_probability <= 0:
        return None
    return 1.0 / model_probability


def odds_source_verified(row: Mapping[str, Any], odds: float | None) -> bool:
    if odds is None or odds <= 1.0:
        return False
    source = ' '.join(str(row.get(key, '') or '') for key in ('odds_source', 'bookmaker', 'sportsbook', 'book', 'data_source')).lower()
    if any(token in source for token in BAD_SOURCE_TOKENS):
        return False
    audit = str(row.get('odds_audit_status', '') or '').strip().lower()
    if audit and audit not in OK_AUDIT_TOKENS:
        return False
    return True


def odds_market_fresh(row: Mapping[str, Any], *, max_age_minutes: int = 180) -> bool:
    status = ' '.join(str(row.get(key, '') or '') for key in ('market_freshness_status', 'odds_freshness_status', 'edge_status', 'odds_audit_status')).lower()
    if 'stale' in status or 'expired' in status:
        return False
    timestamp = row.get('odds_timestamp') or row.get('price_timestamp') or row.get('prediction_timestamp')
    if not timestamp:
        return True
    text = str(timestamp).strip()
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds()
    return age_seconds <= max_age_minutes * 60


def assess_value_pick(
    row: Mapping[str, Any],
    *,
    min_confidence: float = 0.50,
    edge_buffer: float = 0.0,
    ev_buffer: float = 0.0,
    safety_margin: float = 0.02,
    max_age_minutes: int = 180,
) -> ValueAssessment:
    odds = decimal_odds_from(row)
    model_prob = model_probability_from(row)
    raw_implied = raw_implied_probability(odds)
    no_vig = no_vig_probability_from(row, raw_implied)
    edge = None if model_prob is None or raw_implied is None else model_prob - raw_implied
    no_vig_edge = None if model_prob is None or no_vig is None else model_prob - no_vig
    ev = None if model_prob is None or odds is None else model_prob * odds - 1.0
    fair = fair_odds(model_prob)
    target = None if fair is None else fair + float(safety_margin)
    verified = odds_source_verified(row, odds)
    fresh = odds_market_fresh(row, max_age_minutes=max_age_minutes)

    if odds is None or not verified:
        color = 'DATA WARNING'
        recommendation = 'DATA WARNING'
        reason = 'missing_or_unverified_odds'
    elif not fresh:
        color = 'DATA WARNING'
        recommendation = 'DATA WARNING'
        reason = 'stale_odds'
    elif model_prob is None:
        color = 'DATA WARNING'
        recommendation = 'DATA WARNING'
        reason = 'missing_model_probability'
    elif edge is None or ev is None:
        color = 'DATA WARNING'
        recommendation = 'DATA WARNING'
        reason = 'edge_or_ev_unavailable'
    elif model_prob >= min_confidence and edge > edge_buffer and ev > ev_buffer:
        color = 'GREEN'
        recommendation = 'PLAYABLE_VALUE'
        reason = 'positive_ev_and_edge_after_safety_checks'
    elif model_prob >= min_confidence and (edge > -0.025 or ev > -0.025):
        color = 'YELLOW'
        recommendation = 'WATCHLIST'
        reason = 'likely_but_price_not_good_enough'
    else:
        color = 'RED'
        recommendation = 'AVOID'
        reason = 'negative_edge_or_negative_ev'

    rank_score = 0.0
    if color == 'GREEN':
        rank_score += 1000.0
    elif color == 'YELLOW':
        rank_score += 250.0
    elif color == 'DATA WARNING':
        rank_score -= 250.0
    else:
        rank_score -= 500.0
    rank_score += max(-1.0, min(1.0, ev or -1.0)) * 200.0
    rank_score += max(-1.0, min(1.0, edge or -1.0)) * 150.0
    rank_score += (model_prob or 0.0) * 50.0
    if verified:
        rank_score += 20.0
    if fresh:
        rank_score += 20.0

    return ValueAssessment(
        model_probability=model_prob,
        decimal_odds=odds,
        raw_implied_probability=raw_implied,
        no_vig_implied_probability=no_vig,
        edge=edge,
        no_vig_edge=no_vig_edge,
        expected_value=ev,
        fair_odds=fair,
        target_odds=target,
        odds_verified=verified,
        market_fresh=fresh,
        color=color,
        recommendation=recommendation,
        reason=reason,
        rank_score=rank_score,
    )


def all_red_diagnostic(assessments: Iterable[ValueAssessment]) -> str:
    items = list(assessments)
    if not items:
        return 'market_data_missing'
    if any(item.color == 'GREEN' for item in items):
        return 'positive_ev_available'
    if all(item.color == 'DATA WARNING' for item in items):
        return 'market_data_missing_or_stale'
    if any(item.reason == 'likely_but_price_not_good_enough' for item in items):
        return 'picks_likely_but_overpriced'
    if all((item.expected_value is not None and item.expected_value <= 0) for item in items if item.color != 'DATA WARNING'):
        return 'board_has_no_positive_ev_at_current_prices'
    return 'no_green_pick_after_safety_buffers'
