from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .audit import parse_float
from .line_movement import analyze_line_row
from .row_normalizer import normalize_frame, safe_text

MINIMUM_EDGE = 0.035
STRONG_EDGE = 0.075
HIGH_PROBABILITY = 0.62
DRAW_MIN_EDGE = 0.065
DRAW_STRONG_EDGE = 0.095
DRAW_MIN_BOOKS = 4
DRAW_MAX_STAKE_UNITS = 0.25
ULTRA80_TARGET_PROBABILITY = 0.80
ULTRA80_MIN_MODEL_PROBABILITY = 0.80
ULTRA80_MIN_DECIMAL_PRICE = 1.27
ULTRA80_MAX_DECIMAL_PRICE = 1.75
ULTRA80_MIN_EXPECTED_VALUE = 0.025
ULTRA80_MIN_EDGE = 0.075
ULTRA80_MIN_BOOKS = 6
ULTRA80_MIN_API_COVERAGE = 0.66
ULTRA80_MIN_AGENT_SCORE = 70.0
ULTRA80_MAX_STAKE_UNITS = 0.35
TERMINAL_RESULTS = {'win', 'loss', 'void'}
DECISION_ORDER = {'play_strong': 1, 'play_small': 2, 'watch_only': 3, 'no_action': 4, 'review_needed': 5}
DRAW_NAMES = {'draw', 'tie', 'empate', 'x', 'the_draw', 'match_draw'}
DRAW_MARKET_HINTS = {'h2h', 'moneyline', '1x2', 'match_winner', 'winner'}


def implied_probability(decimal_price: Any) -> float | None:
    price = parse_float(decimal_price)
    if price is None or price <= 1.0:
        return None
    return round(1.0 / price, 6)


def clean_probability(value: Any) -> float | None:
    prob = parse_float(value)
    if prob is None:
        return None
    if prob > 1.0:
        prob = prob / 100.0
    if 0.0 < prob < 1.0:
        return round(prob, 6)
    return None


def clean_number(value: Any) -> float | None:
    parsed = parse_float(value)
    if parsed is None:
        return None
    return float(parsed)


def clean_token(value: Any) -> str:
    return safe_text(value).lower().strip().replace('-', '_').replace(' ', '_')


def is_draw_prediction(row: dict[str, Any]) -> bool:
    prediction = clean_token(row.get('prediction'))
    market_type = clean_token(row.get('market_type'))
    if prediction not in DRAW_NAMES:
        return False
    if not market_type:
        return True
    return market_type in DRAW_MARKET_HINTS or 'h2h' in market_type or 'winner' in market_type


def parse_int(value: Any) -> int | None:
    parsed = parse_float(value)
    if parsed is None:
        return None
    try:
        return int(round(float(parsed)))
    except Exception:
        return None


def event_timing_status(row: dict[str, Any], *, now_utc: datetime | None = None) -> str:
    now = now_utc or datetime.now(timezone.utc)
    start = parse_datetime_utc(row.get('event_start_utc'))
    prediction_time = parse_datetime_utc(row.get('prediction_timestamp'))
    if start is None:
        return 'missing_event_start'
    if prediction_time is not None and prediction_time >= start:
        return 'prediction_timestamp_not_before_start'
    if now >= start and prediction_time is None:
        return 'event_already_started_without_prediction_timestamp'
    if now >= start:
        return 'event_already_started'
    if prediction_time is None:
        return 'future_event_not_locked_yet'
    return 'prediction_before_start'


def parse_datetime_utc(value: Any) -> datetime | None:
    text = safe_text(value)
    if not text:
        return None
    try:
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def field_coverage_score(row: dict[str, Any]) -> float:
    fields = ['event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price', 'bookmaker', 'odds_source', 'prediction_timestamp', 'event_start_utc']
    present = sum(1 for field in fields if safe_text(row.get(field)))
    return round(present / len(fields), 6)


def can_lock_candidate(row: dict[str, Any], *, now_utc: datetime | None = None) -> bool:
    required = ['event', 'prediction', 'model_probability', 'decimal_price', 'event_start_utc']
    if not all(safe_text(row.get(field)) for field in required):
        return False
    start = parse_datetime_utc(row.get('event_start_utc'))
    prediction_time = parse_datetime_utc(row.get('prediction_timestamp'))
    if start is None:
        return False
    if prediction_time is not None:
        return prediction_time < start
    status = event_timing_status(row, now_utc=now_utc)
    return status == 'future_event_not_locked_yet'


def stake_guidance(decision: str, score: float, locked: bool, *, draw_risk: bool = False, ultra80: bool = False) -> float:
    if ultra80:
        base = ULTRA80_MAX_STAKE_UNITS
    elif decision == 'play_strong':
        base = 1.0 if score >= 65.0 else 0.75
    elif decision == 'play_small':
        base = 0.35 if score >= 50.0 else 0.25
    else:
        base = 0.0
    if draw_risk and base > 0:
        base = min(base, DRAW_MAX_STAKE_UNITS)
    if base > 0 and not locked:
        base = min(base, 0.25)
    return round(base, 3)


def odds_quality_context(row: dict[str, Any]) -> dict[str, Any]:
    quality = clean_number(row.get('odds_accuracy_score'))
    ev = clean_number(row.get('expected_value_per_unit'))
    edge_override = clean_number(row.get('edge_probability'))
    action = safe_text(row.get('recommended_action')).lower()
    rating = safe_text(row.get('value_rating')).lower()
    trust_grade = safe_text(row.get('odds_trust_grade'))
    flags = safe_text(row.get('odds_quality_flags'))
    return {'odds_accuracy_score': quality, 'expected_value_per_unit': ev, 'edge_probability': edge_override, 'recommended_action': action, 'value_rating': rating, 'odds_trust_grade': trust_grade, 'odds_quality_flags': flags}


def normalized_api_coverage(row: dict[str, Any]) -> float:
    coverage = clean_number(row.get('api_coverage_score'))
    if coverage is None:
        return 0.0
    if coverage > 1.0:
        coverage /= 100.0
    return max(0.0, min(1.0, coverage))


def expected_value(model_prob: float | None, decimal_price: float | None) -> float | None:
    if model_prob is None or decimal_price is None or decimal_price <= 1.0:
        return None
    return round(model_prob * decimal_price - 1.0, 6)


def profit_at_target(decimal_price: float | None, target_probability: float = ULTRA80_TARGET_PROBABILITY) -> float | None:
    if decimal_price is None or decimal_price <= 1.0:
        return None
    return round(target_probability * decimal_price - 1.0, 6)


def ultra80_guardrails(
    row: dict[str, Any],
    *,
    model_prob: float | None,
    market_prob: float | None,
    edge: float | None,
    expected_ev: float | None,
    score: float,
    decision: str,
    draw_risk: bool,
    books: int,
    line_signal: str,
    timing: str,
    result_status: str,
    odds_quality: float | None,
) -> dict[str, Any]:
    decimal_price = clean_number(row.get('decimal_price')) or clean_number(row.get('best_price'))
    api_coverage = normalized_api_coverage(row)
    pattern_signal = clean_number(row.get('pattern_ara_memory_signal'))
    if pattern_signal is None:
        pattern_signal = clean_number(row.get('ara_memory_signal'))
    pattern_signal = float(pattern_signal or 0.0)
    target_profit = profit_at_target(decimal_price)
    required_win_rate = None if decimal_price is None or decimal_price <= 1.0 else round(1.0 / decimal_price, 6)
    reasons: list[str] = []
    signals: list[str] = []
    if model_prob is None or model_prob < ULTRA80_MIN_MODEL_PROBABILITY:
        reasons.append('ultra80_model_probability_below_80')
    if decimal_price is None or decimal_price < ULTRA80_MIN_DECIMAL_PRICE:
        reasons.append('ultra80_price_below_profit_floor')
    if decimal_price is not None and decimal_price > ULTRA80_MAX_DECIMAL_PRICE:
        reasons.append('ultra80_price_too_high_for_consistency')
    if required_win_rate is not None and model_prob is not None:
        signals.append(f'profit_break_even={required_win_rate:.3f}')
    if edge is None or edge < ULTRA80_MIN_EDGE:
        reasons.append('ultra80_edge_below_minimum')
    if expected_ev is None or expected_ev < ULTRA80_MIN_EXPECTED_VALUE:
        reasons.append('ultra80_expected_value_below_minimum')
    if target_profit is None or target_profit <= 0.0:
        reasons.append('ultra80_not_profitable_at_80_percent')
    if books < ULTRA80_MIN_BOOKS:
        reasons.append('ultra80_not_enough_books')
    if api_coverage < ULTRA80_MIN_API_COVERAGE:
        reasons.append('ultra80_api_coverage_too_low')
    if draw_risk:
        reasons.append('ultra80_blocks_draws')
    if line_signal == 'negative':
        reasons.append('ultra80_negative_line_movement')
    if result_status in TERMINAL_RESULTS:
        reasons.append('ultra80_historical_result_present')
    if timing in {'prediction_timestamp_not_before_start', 'event_already_started_without_prediction_timestamp', 'missing_event_start'}:
        reasons.append(f'ultra80_bad_timing_{timing}')
    if odds_quality is not None and odds_quality < 70.0:
        reasons.append('ultra80_odds_quality_below_70')
    if pattern_signal < -0.005:
        reasons.append('ultra80_negative_memory_pattern')
    if decision not in {'play_strong', 'play_small'}:
        reasons.append('ultra80_not_playable_general_decision')
    if score < ULTRA80_MIN_AGENT_SCORE:
        reasons.append('ultra80_agent_score_too_low')
    if model_prob is not None:
        signals.append(f'ultra80_model_prob={model_prob:.3f}')
    if edge is not None:
        signals.append(f'ultra80_edge={edge:.3f}')
    if expected_ev is not None:
        signals.append(f'ultra80_ev={expected_ev:.3f}')
    if target_profit is not None:
        signals.append(f'profit_at_80={target_profit:.3f}')
    signals.append(f'api_coverage={api_coverage:.3f}')
    signals.append(f'books={books}')
    candidate = not reasons
    return {
        'ultra80_candidate': bool(candidate),
        'ultra80_profit_mode': 'PASS' if candidate else 'FAIL',
        'ultra80_reasons': ' | '.join(reasons),
        'ultra80_signals': ' | '.join(signals),
        'ultra80_target_probability': ULTRA80_TARGET_PROBABILITY,
        'ultra80_required_win_rate': required_win_rate,
        'ultra80_profit_at_80_percent': target_profit,
        'ultra80_min_decimal_price': ULTRA80_MIN_DECIMAL_PRICE,
        'ultra80_min_expected_value': ULTRA80_MIN_EXPECTED_VALUE,
        'ultra80_min_edge': ULTRA80_MIN_EDGE,
        'ultra80_min_books': ULTRA80_MIN_BOOKS,
        'ultra80_api_coverage': api_coverage,
        'ultra80_pattern_signal': pattern_signal,
    }


def evaluate_row(row: dict[str, Any], *, min_edge: float = MINIMUM_EDGE, strong_edge: float = STRONG_EDGE, now_utc: datetime | None = None) -> dict[str, Any]:
    model_prob = clean_probability(row.get('model_probability'))
    decimal_price = clean_number(row.get('decimal_price')) or clean_number(row.get('best_price'))
    market_prob = implied_probability(decimal_price)
    coverage = field_coverage_score(row)
    line = analyze_line_row(row)
    timing = event_timing_status(row, now_utc=now_utc)
    has_lock_time = bool(safe_text(row.get('prediction_timestamp')))
    result_status = safe_text(row.get('result_status')).lower()
    lock_ready = can_lock_candidate(row, now_utc=now_utc)
    odds_ctx = odds_quality_context(row)
    odds_quality = odds_ctx['odds_accuracy_score']
    expected_ev = odds_ctx['expected_value_per_unit']
    odds_action = odds_ctx['recommended_action']
    value_rating = odds_ctx['value_rating']
    trust_grade = odds_ctx['odds_trust_grade']
    draw_risk = is_draw_prediction(row)
    books = parse_int(row.get('bookmaker_count')) or parse_int(row.get('books')) or 0
    reasons: list[str] = []
    signals: list[str] = []
    if draw_risk:
        signals.append('draw_market_candidate')
        if books and books < DRAW_MIN_BOOKS:
            reasons.append('draw_needs_more_books')
        elif books == 0:
            reasons.append('draw_missing_book_count')
    if result_status in TERMINAL_RESULTS:
        reasons.append('historical_result_present')
    if not safe_text(row.get('event')):
        reasons.append('missing_event')
    if not safe_text(row.get('prediction')):
        reasons.append('missing_prediction')
    if model_prob is None:
        reasons.append('missing_model_probability')
    if market_prob is None:
        reasons.append('missing_decimal_price')
    if not safe_text(row.get('bookmaker')):
        reasons.append('missing_bookmaker')
    if not safe_text(row.get('odds_source')):
        reasons.append('missing_odds_source')
    if not safe_text(row.get('event_start_utc')):
        reasons.append('missing_event_start')
    if not has_lock_time:
        signals.append('not_locked_yet')
    if lock_ready:
        signals.append('lock_ready')
    if timing == 'prediction_timestamp_not_before_start':
        reasons.append('prediction_timestamp_not_before_start')
    elif timing == 'event_already_started_without_prediction_timestamp':
        reasons.append('event_already_started_without_prediction_timestamp')
    elif timing == 'event_already_started':
        signals.append('event_already_started')
    elif timing == 'future_event_not_locked_yet':
        signals.append('future_event_not_locked_yet')
    elif timing == 'prediction_before_start':
        signals.append('prediction_before_start')
    if coverage < 0.70:
        reasons.append('low_field_coverage')
    edge = None if model_prob is None or market_prob is None else round(model_prob - market_prob, 6)
    if odds_ctx['edge_probability'] is not None:
        edge = round(float(odds_ctx['edge_probability']), 6)
        signals.append('odds_accuracy_edge_used')
    if expected_ev is None:
        expected_ev = expected_value(model_prob, decimal_price)
        if expected_ev is not None:
            signals.append('model_price_ev_used')
    if draw_risk and edge is not None:
        effective_draw_min = max(float(min_edge), DRAW_MIN_EDGE)
        signals.append(f'draw_edge_required={effective_draw_min:.3f}')
        if edge < effective_draw_min:
            reasons.append('draw_edge_below_minimum')
        if model_prob is not None and model_prob < 0.20:
            reasons.append('draw_probability_too_low')
    edge_percent = None if edge is None else round(edge * 100.0, 3)
    if edge is not None:
        signals.append(f'edge={edge:.3f}')
        if edge < 0:
            reasons.append('negative_edge')
        elif edge < min_edge:
            reasons.append('edge_below_minimum')
        elif edge >= strong_edge:
            signals.append('strong_edge')
        else:
            signals.append('positive_edge')
    if expected_ev is not None:
        signals.append(f'ev={expected_ev:.3f}')
        if expected_ev <= -0.02:
            reasons.append('negative_expected_value')
        elif expected_ev > 0:
            signals.append('positive_expected_value')
    if odds_quality is not None:
        signals.append(f'odds_quality={odds_quality:.0f}')
        if odds_quality < 50:
            reasons.append('weak_odds_quality')
        elif odds_quality >= 80:
            signals.append('strong_odds_quality')
    if odds_action in {'needs_more_info', 'rescan_prices'}:
        reasons.append(odds_action)
    elif odds_action == 'lock_candidate':
        signals.append('odds_lock_candidate')
    if value_rating:
        signals.append(f'value_rating={value_rating}')
    if trust_grade:
        signals.append(f'odds_grade={trust_grade}')
    if 'manual-review' in trust_grade.lower() or value_rating == 'manual_review_needed':
        reasons.append('manual_review_needed')
    line_signal = line.get('line_value_signal', 'unknown')
    if line_signal == 'positive':
        signals.append('positive_line_movement')
    elif line_signal == 'negative':
        reasons.append('negative_line_movement')
    elif line.get('line_status') != 'ready':
        signals.append('line_movement_unavailable')
    critical_missing = {'missing_event', 'missing_prediction', 'missing_model_probability', 'missing_decimal_price'}
    source_missing = {'missing_bookmaker', 'missing_odds_source'}
    hard_no_action = {'historical_result_present', 'prediction_timestamp_not_before_start', 'event_already_started_without_prediction_timestamp'}
    draw_blockers = {'draw_needs_more_books', 'draw_missing_book_count', 'draw_edge_below_minimum', 'draw_probability_too_low'}
    if any(reason in reasons for reason in critical_missing):
        decision = 'review_needed'
    elif any(reason in reasons for reason in hard_no_action):
        decision = 'no_action'
    elif any(reason in reasons for reason in {'negative_edge', 'negative_expected_value', 'weak_odds_quality'}):
        decision = 'no_action'
    elif any(reason in reasons for reason in {'needs_more_info', 'rescan_prices', 'manual_review_needed'}):
        decision = 'watch_only'
    elif draw_risk and any(reason in reasons for reason in draw_blockers):
        decision = 'watch_only'
    elif 'low_field_coverage' in reasons:
        decision = 'no_action'
    elif any(reason in reasons for reason in source_missing):
        decision = 'watch_only'
    elif 'edge_below_minimum' in reasons or 'negative_line_movement' in reasons:
        decision = 'watch_only'
    elif draw_risk and edge is not None and edge >= max(float(strong_edge), DRAW_STRONG_EDGE) and model_prob is not None and model_prob >= 0.28:
        decision = 'play_small'
    elif edge is not None and edge >= strong_edge and model_prob is not None and model_prob >= max(HIGH_PROBABILITY, 0.66) and expected_ev is not None and expected_ev > 0:
        decision = 'play_strong'
    elif edge is not None and edge >= min_edge and (expected_ev is None or expected_ev > -0.02):
        decision = 'play_small'
    else:
        decision = 'watch_only'
    score = 0.0
    if model_prob is not None:
        score += model_prob * 40.0
    if edge is not None:
        score += max(-0.10, min(0.15, edge)) * 250.0
    if expected_ev is not None:
        score += max(-0.10, min(0.15, expected_ev)) * 80.0
    score += coverage * 20.0
    if odds_quality is not None:
        score += max(-10.0, min(10.0, (odds_quality - 60.0) / 4.0))
    if line_signal == 'positive':
        score += 7.5
    elif line_signal == 'negative':
        score -= 7.5
    if has_lock_time:
        score += 5.0
    if timing == 'prediction_before_start':
        score += 5.0
    if draw_risk:
        score -= 8.0
        if decision == 'play_strong':
            decision = 'play_small'
        signals.append('draw_stake_capped')
    if decision == 'review_needed':
        score = min(score, 35.0)
    if decision == 'no_action':
        score = min(score, 45.0)
    if decision == 'watch_only':
        score = min(score, 55.0)
    score = round(max(0.0, min(100.0, score)), 3)
    ultra = ultra80_guardrails(
        row,
        model_prob=model_prob,
        market_prob=market_prob,
        edge=edge,
        expected_ev=expected_ev,
        score=score,
        decision=decision,
        draw_risk=draw_risk,
        books=books,
        line_signal=line_signal,
        timing=timing,
        result_status=result_status,
        odds_quality=odds_quality,
    )
    if ultra['ultra80_candidate']:
        decision = 'play_strong'
        score = max(score, ULTRA80_MIN_AGENT_SCORE)
        signals.append('ultra80_profitable_candidate')
    return {
        'agent_decision': decision,
        'agent_score': score,
        'decision_rank': DECISION_ORDER.get(decision, 99),
        'event_timing_status': timing,
        'lock_ready': bool(lock_ready),
        'already_locked': bool(has_lock_time),
        'recommended_stake_units': stake_guidance(decision, score, has_lock_time, draw_risk=draw_risk, ultra80=bool(ultra['ultra80_candidate'])),
        'model_probability_clean': model_prob,
        'market_implied_probability': market_prob,
        'model_market_edge': edge,
        'model_market_edge_percent': edge_percent,
        'expected_value_per_unit': expected_ev,
        'profit_at_80_percent': ultra['ultra80_profit_at_80_percent'],
        'field_coverage_score': coverage,
        'line_value_signal': line_signal,
        'is_draw_prediction': bool(draw_risk),
        'draw_guardrail': 'strict_draw_rules_applied' if draw_risk else '',
        **ultra,
        'decision_reasons': ' | '.join(sorted(set(reasons))),
        'decision_signals': ' | '.join(signals),
    }


def build_agent_decisions(frame: pd.DataFrame, *, min_edge: float = MINIMUM_EDGE, strong_edge: float = STRONG_EDGE, now_utc: datetime | None = None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = normalize_frame(frame)
    rows: list[dict[str, Any]] = []
    for row in data.to_dict(orient='records'):
        item = dict(row)
        item.update(evaluate_row(row, min_edge=min_edge, strong_edge=strong_edge, now_utc=now_utc))
        rows.append(item)
    result = pd.DataFrame(rows)
    if {'decision_rank', 'agent_score'}.issubset(result.columns):
        result = result.sort_values(['decision_rank', 'agent_score'], ascending=[True, False])
    return result


def playable_candidates(frame: pd.DataFrame, *, min_edge: float = MINIMUM_EDGE, strong_edge: float = STRONG_EDGE) -> pd.DataFrame:
    decisions = build_agent_decisions(frame, min_edge=min_edge, strong_edge=strong_edge)
    if decisions.empty:
        return pd.DataFrame()
    decision = decisions['agent_decision'].fillna('').astype(str)
    return decisions[decision.isin(['play_strong', 'play_small'])].copy()


def ultra80_candidates(frame: pd.DataFrame, *, min_edge: float = MINIMUM_EDGE, strong_edge: float = STRONG_EDGE) -> pd.DataFrame:
    decisions = build_agent_decisions(frame, min_edge=min_edge, strong_edge=strong_edge)
    if decisions.empty or 'ultra80_candidate' not in decisions.columns:
        return pd.DataFrame()
    return decisions[decisions['ultra80_candidate'].fillna(False).astype(bool)].copy()


def lock_ready_candidates(frame: pd.DataFrame, *, min_edge: float = MINIMUM_EDGE, strong_edge: float = STRONG_EDGE) -> pd.DataFrame:
    candidates = playable_candidates(frame, min_edge=min_edge, strong_edge=strong_edge)
    if candidates.empty or 'lock_ready' not in candidates.columns:
        return pd.DataFrame()
    return candidates[candidates['lock_ready'].astype(bool)].copy()


def agent_decision_summary(frame: pd.DataFrame, *, min_edge: float = MINIMUM_EDGE, strong_edge: float = STRONG_EDGE) -> dict[str, Any]:
    decisions = build_agent_decisions(frame, min_edge=min_edge, strong_edge=strong_edge)
    if decisions.empty:
        return {'rows': 0, 'play_strong': 0, 'play_small': 0, 'watch_only': 0, 'no_action': 0, 'review_needed': 0, 'lock_ready_candidates': 0, 'recommended_total_stake_units': 0.0, 'average_score': None, 'draw_candidates': 0, 'ultra80_candidates': 0, 'ultra80_avg_profit_at_80': None}
    decision = decisions['agent_decision'].fillna('').astype(str)
    ultra80 = decisions.get('ultra80_candidate', pd.Series(dtype=bool)).fillna(False).astype(bool)
    profit80 = pd.to_numeric(decisions.get('profit_at_80_percent', pd.Series(dtype=float)), errors='coerce')
    ultra_profit = profit80[ultra80.reindex(profit80.index, fill_value=False)] if not profit80.empty else pd.Series(dtype=float)
    return {
        'rows': int(len(decisions)),
        'play_strong': int(decision.eq('play_strong').sum()),
        'play_small': int(decision.eq('play_small').sum()),
        'watch_only': int(decision.eq('watch_only').sum()),
        'no_action': int(decision.eq('no_action').sum()),
        'review_needed': int(decision.eq('review_needed').sum()),
        'lock_ready_candidates': int(decisions.get('lock_ready', pd.Series(dtype=bool)).fillna(False).astype(bool).sum()),
        'recommended_total_stake_units': round(float(pd.to_numeric(decisions.get('recommended_stake_units', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()), 3),
        'average_score': round(float(pd.to_numeric(decisions['agent_score'], errors='coerce').fillna(0).mean()), 3),
        'draw_candidates': int(decisions.get('is_draw_prediction', pd.Series(dtype=bool)).fillna(False).astype(bool).sum()),
        'ultra80_candidates': int(ultra80.sum()),
        'ultra80_avg_profit_at_80': None if ultra_profit.empty else round(float(ultra_profit.mean()), 6),
    }
