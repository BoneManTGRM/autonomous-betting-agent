from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from .odds_lock_tools import lock_status, now_utc, parse_datetime_utc, profit_units, proof_hash, proof_id_from_hash
from .row_normalizer import normalize_frame, safe_text

UNSUPPORTED_TERMS = ('tennis', 'atp', 'wta', 'itf', 'challenger')


def _clean(value: Any) -> str:
    return ' '.join(str(value or '').lower().replace('-', ' ').replace('_', ' ').split())


def is_unsupported_market(row: Mapping[str, Any]) -> bool:
    text = _clean(' '.join([
        safe_text(row.get('sport')),
        safe_text(row.get('sport_key')),
        safe_text(row.get('league')),
        safe_text(row.get('market_type')),
        safe_text(row.get('event')),
    ]))
    return any(term in text for term in UNSUPPORTED_TERMS)


def _safe_float(value: Any, default: float = 1.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(parsed):
        return default
    return parsed


def lock_all_high_confidence_rows(
    frame: pd.DataFrame | list[dict[str, Any]],
    *,
    analyst: str = 'ABA Signal Pro · Powered by Reparodynamics',
    workspace_id: str = 'test_01',
    max_units: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create internal all-high-confidence proof rows without applying +EV filters.

    This is for large-sample accuracy testing. It keeps public proof honest by marking
    rows as internal/research, not official +EV. Unsupported tennis-style rows are
    rejected instead of locked.
    """
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if normalized.empty:
        return pd.DataFrame(), pd.DataFrame()

    locked_time = now_utc()
    locked_dt = parse_datetime_utc(locked_time)
    locked_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []

    for row in normalized.to_dict(orient='records'):
        item = dict(row)
        if is_unsupported_market(item):
            item['reject_reason'] = 'REJECT_UNSUPPORTED_MARKET'
            rejected_rows.append(item)
            continue

        item['locked_at_utc'] = locked_time
        item['analyst'] = analyst or 'ABA Signal Pro · Powered by Reparodynamics'
        item['test_window_id'] = workspace_id or 'test_01'
        item['ledger_type'] = 'all_high_confidence_internal_test'
        item['official_ev_pick'] = False
        item['official_lock_ready'] = False
        item['research_lock_ready'] = True
        item['public_confidence'] = 'High Confidence Internal Test'
        item['public_reason'] = 'All reviewed high-confidence row accepted for internal proof-volume testing; not official +EV proof.'
        item['lock_blockers'] = safe_text(item.get('lock_blockers'))
        item['stake_units'] = round(max(0.0, min(float(max_units), _safe_float(item.get('stake_units') or item.get('recommended_stake_units'), 1.0))), 2)
        item['proof_status'] = lock_status(item, locked_at=locked_dt)
        item['profit_units'] = profit_units(item)
        item['proof_hash'] = proof_hash(item)
        item['proof_id'] = proof_id_from_hash(item['proof_hash'])
        locked_rows.append(item)

    return pd.DataFrame(locked_rows), pd.DataFrame(rejected_rows)
