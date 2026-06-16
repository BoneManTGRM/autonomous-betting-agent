from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .odds_lock_tools import lock_blockers, parse_datetime_utc
from .row_normalizer import normalize_frame, probability_value, safe_text

PRIVATE_ONLY_COLUMNS = {
    'api_context_error',
    'api_sources_missing',
    'configured_api_sources',
    'decision_reasons',
    'decision_signals',
    'fusion_reason',
    'fusion_warning',
    'manual_context_notes',
    'manual_probability_adjustment',
    'model_probability_before_manual',
    'raw_api_payload',
    'scanner_reasons',
    'source_file',
}

CLIENT_SAFE_COLUMNS = [
    'proof_id',
    'locked_at_utc',
    'event_start_utc',
    'event',
    'sport',
    'market_type',
    'prediction',
    'decimal_price',
    'bookmaker',
    'model_probability',
    'market_implied_probability',
    'edge_percent',
    'expected_value_percent',
    'confidence_tier',
    'odds_trust_grade',
    'recommended_action',
    'public_explanation',
    'result_status',
    'final_score',
    'profit_units',
]


def _num(value: Any) -> float | None:
    try:
        parsed = float(str(value).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _future_event(row: dict[str, Any], now: datetime | None = None) -> bool:
    parsed = parse_datetime_utc(row.get('event_start_utc'))
    if parsed is None:
        return False
    return parsed > (now or datetime.now(timezone.utc))


def confidence_tier(row: dict[str, Any]) -> str:
    grade = safe_text(row.get('odds_trust_grade')).upper()
    action = safe_text(row.get('recommended_action')).lower()
    agent_decision = safe_text(row.get('agent_decision')).lower()
    quality = _num(row.get('odds_accuracy_score')) or 0.0
    ev = _num(row.get('expected_value_per_unit'))
    edge = _num(row.get('edge_probability') or row.get('model_market_edge'))
    if grade == 'A+' or (action == 'lock_candidate' and quality >= 85 and ev is not None and ev > 0.08):
        return 'A+'
    if grade == 'A' or (agent_decision == 'play_strong' and quality >= 75 and edge is not None and edge >= 0.04):
        return 'A'
    if grade == 'B' or agent_decision == 'play_small':
        return 'B'
    if action in {'needs_more_info', 'rescan_prices'} or 'review' in grade.lower():
        return 'C'
    return 'D'


def proof_eligibility(row: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    blockers = lock_blockers(row, require_future=True, locked_at=now or datetime.now(timezone.utc))
    has_proof = bool(safe_text(row.get('proof_id')) and safe_text(row.get('locked_at_utc')))
    future = _future_event(row, now=now)
    eligible = not blockers
    return {
        'official_proof_eligible': bool(eligible),
        'already_locked_proof': has_proof,
        'future_event': future,
        'proof_blockers': '; '.join(blockers),
        'missing_for_proof': '; '.join([item.replace('missing_', '').replace('invalid_', '') for item in blockers if item.startswith(('missing_', 'invalid_'))]),
    }


def do_not_lock_warnings(row: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    flags = safe_text(row.get('odds_quality_flags'))
    action = safe_text(row.get('recommended_action')).lower()
    rating = safe_text(row.get('value_rating')).lower()
    manual_risk = safe_text(row.get('manual_context_risk'))
    quality = _num(row.get('odds_accuracy_score'))
    ev = _num(row.get('expected_value_per_unit'))
    book_count = _num(row.get('book_count_normalized') or row.get('bookmaker_count') or row.get('books')) or 0
    if not _future_event(row):
        warnings.append('event_not_future')
    if quality is not None and quality < 60:
        warnings.append('weak_odds_quality')
    if ev is not None and ev < 0:
        warnings.append('negative_expected_value')
    if book_count < 2:
        warnings.append('low_book_coverage')
    if 'high_market_hold' in flags:
        warnings.append('high_market_hold')
    if 'wide_price_range' in flags:
        warnings.append('wide_price_range')
    if manual_risk and manual_risk not in {'ok'}:
        warnings.append(manual_risk)
    if action in {'needs_more_info', 'rescan_prices', 'skip'}:
        warnings.append(action)
    if rating in {'negative_value', 'data_too_weak'}:
        warnings.append(rating)
    return sorted(set(warnings))


def explain_pick(row: dict[str, Any]) -> str:
    pick = safe_text(row.get('prediction')) or 'the selected side'
    event = safe_text(row.get('event')) or 'this event'
    probability = probability_value(row, 'model_probability')
    implied = _num(row.get('market_implied_probability'))
    edge = _num(row.get('edge_percent'))
    ev = _num(row.get('expected_value_percent'))
    grade = safe_text(row.get('odds_trust_grade')) or safe_text(row.get('confidence_tier'))
    action = safe_text(row.get('recommended_action')) or safe_text(row.get('agent_decision'))
    quality = _num(row.get('odds_accuracy_score'))
    parts = [f'{pick} in {event}.']
    if probability is not None:
        parts.append(f'Model probability {probability * 100:.1f}%.')
    if implied is not None:
        parts.append(f'Market implied probability {implied * 100:.1f}%.')
    if edge is not None:
        parts.append(f'Edge {edge:.1f} percentage points.')
    if ev is not None:
        parts.append(f'EV {ev:.1f}% per unit.')
    if quality is not None:
        parts.append(f'Odds quality {quality:.0f}/100.')
    if grade:
        parts.append(f'Trust grade {grade}.')
    if action:
        parts.append(f'Recommended action: {action.replace("_", " ")}.')
    needed = safe_text(row.get('needed_info'))
    if needed:
        parts.append(f'Needed info: {needed}.')
    return ' '.join(parts)


def enrich_safety_columns(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if normalized.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for row in normalized.to_dict(orient='records'):
        item = dict(row)
        item['confidence_tier'] = confidence_tier(item)
        item.update(proof_eligibility(item))
        warnings = do_not_lock_warnings(item)
        item['do_not_lock_warnings'] = '; '.join(warnings)
        item['do_not_lock'] = bool(warnings and not item.get('official_proof_eligible'))
        item['public_explanation'] = explain_pick(item)
        rows.append(item)
    return pd.DataFrame(rows)


def client_safe_frame(frame: pd.DataFrame | list[dict[str, Any]], *, client_safe: bool = True) -> pd.DataFrame:
    enriched = enrich_safety_columns(frame)
    if enriched.empty or not client_safe:
        if enriched.empty:
            return pd.DataFrame()
        return enriched.drop(columns=[col for col in PRIVATE_ONLY_COLUMNS if col in enriched.columns], errors='ignore') if client_safe else enriched
    for column in CLIENT_SAFE_COLUMNS:
        if column not in enriched.columns:
            enriched[column] = ''
    return enriched[[column for column in CLIENT_SAFE_COLUMNS if column in enriched.columns]]


def operator_checklist_frame(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    enriched = enrich_safety_columns(frame)
    total = int(len(enriched)) if not enriched.empty else 0
    eligible = int(enriched.get('official_proof_eligible', pd.Series(dtype=bool)).fillna(False).astype(bool).sum()) if not enriched.empty else 0
    warnings = int(enriched.get('do_not_lock_warnings', pd.Series(dtype=str)).fillna('').astype(str).str.len().gt(0).sum()) if not enriched.empty else 0
    rows = [
        {'check': 'Input rows are loaded', 'status': 'pass' if total > 0 else 'blocker', 'details': f'{total} rows'},
        {'check': 'Highest-confidence or value review completed', 'status': 'pass' if total <= 25 and total > 0 else 'warning', 'details': 'Prefer 10-25 rows before locking'},
        {'check': 'Official proof eligible rows exist', 'status': 'pass' if eligible > 0 else 'blocker', 'details': f'{eligible} eligible rows'},
        {'check': 'Do-not-lock warnings reviewed', 'status': 'pass' if warnings == 0 else 'warning', 'details': f'{warnings} rows have warnings'},
        {'check': 'Client-safe view available', 'status': 'pass', 'details': 'Use client_safe_frame before sharing'},
        {'check': 'Analytics disclaimer', 'status': 'pass', 'details': 'No guaranteed wins or returns'},
    ]
    return pd.DataFrame(rows)


def private_beta_snapshot(frame: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    enriched = enrich_safety_columns(frame)
    if enriched.empty:
        return {'rows': 0, 'eligible': 0, 'warnings': 0, 'a_plus': 0, 'a_tier': 0, 'client_ready': False}
    tiers = enriched.get('confidence_tier', pd.Series(dtype=str)).astype(str)
    eligible = enriched.get('official_proof_eligible', pd.Series(dtype=bool)).fillna(False).astype(bool)
    warnings = enriched.get('do_not_lock_warnings', pd.Series(dtype=str)).fillna('').astype(str).str.len().gt(0)
    return {
        'rows': int(len(enriched)),
        'eligible': int(eligible.sum()),
        'warnings': int(warnings.sum()),
        'a_plus': int(tiers.eq('A+').sum()),
        'a_tier': int(tiers.eq('A').sum()),
        'client_ready': bool(int(eligible.sum()) > 0 and int(warnings.sum()) == 0),
    }
