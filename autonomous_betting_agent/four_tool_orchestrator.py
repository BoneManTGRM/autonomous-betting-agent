from __future__ import annotations

from typing import Any

import pandas as pd

from .row_normalizer import normalize_frame, safe_text

SCANNER_REQUIREMENTS = {
    'event': ['event', 'game', 'match'],
    'sport': ['sport', 'sport_key', 'league'],
    'market_type': ['market_type', 'market', 'prop_type'],
    'prediction': ['prediction', 'pick', 'selection'],
    'decimal_price': ['decimal_price', 'best_price', 'average_price', 'odds', 'price'],
    'bookmaker': ['bookmaker', 'book', 'sportsbook', 'best_bookmaker'],
}
PREDICTOR_REQUIREMENTS = {
    'event': ['event', 'game', 'match'],
    'sport': ['sport', 'sport_key', 'league'],
    'market_type': ['market_type', 'market', 'prop_type'],
    'prediction': ['prediction', 'pick', 'selection'],
    'model_probability': ['model_probability', 'model_probability_clean', 'probability', 'predicted_probability'],
    'decimal_price': ['decimal_price', 'best_price', 'average_price', 'odds', 'price'],
    'event_start_utc': ['event_start_utc', 'known_start_utc', 'start', 'commence_time'],
}
VALUE_REQUIREMENTS = {
    'event': ['event', 'game', 'match'],
    'prediction': ['prediction', 'pick', 'selection'],
    'model_probability': ['model_probability', 'model_probability_clean', 'probability', 'predicted_probability'],
    'decimal_price': ['decimal_price', 'best_price', 'average_price', 'odds', 'price'],
    'agent_decision': ['agent_decision', 'decision'],
}
LEARNING_REQUIREMENTS = {
    'event': ['event', 'game', 'match'],
    'prediction': ['prediction', 'pick', 'selection'],
    'model_probability': ['model_probability', 'model_probability_clean', 'probability', 'predicted_probability', 'confidence_probability'],
    'result_status': ['result_status', 'result', 'outcome', 'win_loss', 'graded_result'],
}
PROBABILITY_COLUMNS = ['model_probability', 'model_probability_clean', 'probability', 'predicted_probability', 'confidence_probability']
RESULT_COLUMNS = ['result_status', 'result', 'outcome', 'win_loss', 'graded_result']


def _column_present(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)
    return frame[column].map(lambda value: bool(safe_text(value)))


def _group_present_rate(frame: pd.DataFrame, aliases: list[str]) -> float:
    if frame is None or frame.empty:
        return 0.0
    present = pd.Series(False, index=frame.index)
    any_alias = False
    for column in aliases:
        if column in frame.columns:
            any_alias = True
            present = present | _column_present(frame, column)
    if not any_alias:
        return 0.0
    return round(float(present.mean()), 6)


def _requirement_coverage(frame: pd.DataFrame, requirements: dict[str, list[str]]) -> float:
    if frame is None or frame.empty or not requirements:
        return 0.0
    rates = [_group_present_rate(frame, aliases) for aliases in requirements.values()]
    return round(float(sum(rates) / len(rates)), 6) if rates else 0.0


def _missing_requirements(frame: pd.DataFrame, requirements: dict[str, list[str]]) -> list[str]:
    if frame is None or frame.empty:
        return list(requirements.keys())
    missing: list[str] = []
    for canonical, aliases in requirements.items():
        if _group_present_rate(frame, aliases) == 0:
            missing.append(canonical)
    return missing


def _count(frame: pd.DataFrame, column: str, value: str) -> int:
    if frame is None or frame.empty or column not in frame.columns:
        return 0
    return int(frame[column].astype(str).str.lower().eq(value.lower()).sum())


def _bool_count(frame: pd.DataFrame, column: str) -> int:
    if frame is None or frame.empty or column not in frame.columns:
        return 0
    values = frame[column].astype(str).str.lower().str.strip()
    return int(values.isin(['true', '1', 'yes', 'y']).sum())


def _numeric_mean(frame: pd.DataFrame, column: str) -> float | None:
    if frame is None or frame.empty or column not in frame.columns:
        return None
    values = pd.to_numeric(frame[column], errors='coerce').dropna()
    if values.empty:
        return None
    return round(float(values.mean()), 6)


def _result_mask(frame: pd.DataFrame) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=bool)
    resolved = pd.Series(False, index=frame.index)
    for column in RESULT_COLUMNS:
        if column in frame.columns:
            values = frame[column].astype(str).str.lower().str.strip()
            resolved = resolved | values.isin(['win', 'won', 'loss', 'lost', '1', '0', '1.0', '0.0'])
    return resolved


def _probability_mask(frame: pd.DataFrame) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=bool)
    usable = pd.Series(False, index=frame.index)
    for column in PROBABILITY_COLUMNS:
        if column not in frame.columns:
            continue
        values = pd.to_numeric(frame[column], errors='coerce')
        values = values.where(values <= 1.0, values / 100.0)
        usable = usable | values.between(0.000001, 0.999999, inclusive='both').fillna(False)
    return usable


def _resolved_count(frame: pd.DataFrame) -> int:
    if frame is None or frame.empty:
        return 0
    return int(_result_mask(frame).sum())


def _probability_count(frame: pd.DataFrame) -> int:
    if frame is None or frame.empty:
        return 0
    return int(_probability_mask(frame).sum())


def _resolved_with_probability_count(frame: pd.DataFrame) -> int:
    if frame is None or frame.empty:
        return 0
    return int((_result_mask(frame) & _probability_mask(frame)).sum())


def _has_any(frame: pd.DataFrame, aliases: list[str]) -> bool:
    return _group_present_rate(frame, aliases) > 0


def page_health(frame: pd.DataFrame | list[dict[str, Any]], *, page: str) -> dict[str, Any]:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    rows = int(len(normalized)) if normalized is not None else 0
    page_key = page.strip().lower().replace(' ', '_')

    scanner_coverage = _requirement_coverage(normalized, SCANNER_REQUIREMENTS)
    predictor_coverage = _requirement_coverage(normalized, PREDICTOR_REQUIREMENTS)
    value_coverage = _requirement_coverage(normalized, VALUE_REQUIREMENTS)
    learning_coverage = _requirement_coverage(normalized, LEARNING_REQUIREMENTS)
    resolved = _resolved_count(normalized)
    probabilities = _probability_count(normalized)
    resolved_with_probability = _resolved_with_probability_count(normalized)
    avg_agent_score = _numeric_mean(normalized, 'agent_score')
    avg_scanner_strength = _numeric_mean(normalized, 'scanner_strength_score')
    playable = _count(normalized, 'agent_decision', 'play_strong') + _count(normalized, 'agent_decision', 'play_small')
    lock_ready = _bool_count(normalized, 'lock_ready')

    if rows == 0:
        status = 'empty'
        next_action = 'run_or_upload_data'
        blockers = ['no_rows']
    elif page_key == 'scanner_pro':
        blockers = _missing_requirements(normalized, SCANNER_REQUIREMENTS)
        status = 'ready_for_pro_predictor' if scanner_coverage >= 0.80 else 'needs_better_scan'
        next_action = 'send_to_pro_predictor' if status == 'ready_for_pro_predictor' else 'rescan_with_more_books_or_sport_keys'
    elif page_key == 'pro_predictor':
        blockers = _missing_requirements(normalized, PREDICTOR_REQUIREMENTS)
        status = 'ready_for_what_are_the_odds' if predictor_coverage >= 0.80 else 'needs_prediction_fields'
        next_action = 'send_to_what_are_the_odds' if status == 'ready_for_what_are_the_odds' else 'rerun_with_odds_and_event_times'
    elif page_key == 'what_are_the_odds':
        blockers = _missing_requirements(normalized, VALUE_REQUIREMENTS)
        status = 'ready_for_lock_or_learning' if playable > 0 or value_coverage >= 0.80 else 'needs_value_review_fields'
        next_action = 'lock_future_plays_or_train_finished_results' if status == 'ready_for_lock_or_learning' else 'add_probabilities_prices_and_decisions'
    elif page_key == 'learning_memory':
        blockers = _missing_requirements(normalized, LEARNING_REQUIREMENTS)
        if resolved_with_probability >= 25:
            status = 'ready_to_train_strongly'
            next_action = 'train_and_save_memory'
        elif resolved_with_probability >= 5:
            status = 'ready_to_train_with_sample_warning'
            next_action = 'train_but_collect_more_results'
        elif resolved >= 5:
            status = 'has_results_but_needs_probabilities'
            next_action = 'add_probabilities_or_prices_before_training'
        else:
            status = 'needs_finished_results'
            next_action = 'add_more_win_loss_results'
    else:
        blockers = []
        status = 'unknown_page'
        next_action = 'review_manually'

    score = 0.0
    if rows > 0:
        score += min(30.0, rows / 10.0)
        score += scanner_coverage * 15.0
        score += predictor_coverage * 20.0
        score += value_coverage * 20.0
        score += min(10.0, playable * 2.0)
        score += min(5.0, resolved_with_probability)
    return {
        'page': page,
        'rows': rows,
        'status': status,
        'next_action': next_action,
        'handoff_score': round(max(0.0, min(100.0, score)), 2),
        'scanner_coverage': scanner_coverage,
        'predictor_coverage': predictor_coverage,
        'value_coverage': value_coverage,
        'learning_coverage': learning_coverage,
        'playable_rows': playable,
        'lock_ready_rows': lock_ready,
        'resolved_rows': resolved,
        'probability_rows': probabilities,
        'resolved_probability_rows': resolved_with_probability,
        'avg_agent_score': avg_agent_score,
        'avg_scanner_strength': avg_scanner_strength,
        'blockers': blockers,
    }


def page_health_frame(frame: pd.DataFrame | list[dict[str, Any]], *, page: str) -> pd.DataFrame:
    health = page_health(frame, page=page)
    flat = dict(health)
    flat['blockers'] = ' | '.join(health.get('blockers', []))
    return pd.DataFrame([flat])


def four_tool_recommendation(frame: pd.DataFrame | list[dict[str, Any]]) -> str:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if normalized.empty:
        return 'start_with_scanner_pro_or_upload_csv'
    if _resolved_with_probability_count(normalized) >= 5:
        return 'learning_memory'
    if 'agent_decision' in normalized.columns and (_count(normalized, 'agent_decision', 'play_strong') + _count(normalized, 'agent_decision', 'play_small')) > 0:
        return 'what_are_the_odds_or_odds_lock'
    if _has_any(normalized, VALUE_REQUIREMENTS['model_probability']) and _has_any(normalized, VALUE_REQUIREMENTS['decimal_price']):
        return 'what_are_the_odds'
    if _has_any(normalized, SCANNER_REQUIREMENTS['decimal_price']):
        return 'pro_predictor'
    return 'scanner_pro'
