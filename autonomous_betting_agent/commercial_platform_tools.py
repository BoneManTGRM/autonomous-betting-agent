from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from .odds_lock_tools import (
    client_view,
    daily_report,
    lock_rows,
    lock_status,
    proof_hash,
    summarize_locked_picks,
    update_profit_columns,
)
from .pick_hold_store import load_held_rows, save_held_rows
from .row_normalizer import normalize_frame, result_status, safe_text

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER_PATH = REPO_ROOT / 'data' / 'odds_lock_pro_ledger.csv'
PROOF_REQUIRED_COLUMNS = {'proof_id', 'locked_at_utc'}
LOCKED_STORE_KEY = 'odds_lock_pro_locked_rows'
REFRESH_STORE_KEY = 'public_proof_dashboard_refresh_rows'


def normalize_workspace_id(value: Any) -> str:
    text = safe_text(value).strip().lower()
    if not text:
        return 'default'
    cleaned = ''.join(char if char.isalnum() or char in {'-', '_'} else '_' for char in text)
    cleaned = '_'.join(part for part in cleaned.split('_') if part)
    return cleaned[:48] or 'default'


def persistent_ledger_path(workspace_id: Any = '', path: Path = DEFAULT_LEDGER_PATH) -> Path:
    workspace = normalize_workspace_id(workspace_id)
    if workspace in {'default', 'shared', 'main'}:
        return path
    return path.with_name(f'{path.stem}_{workspace}{path.suffix}')


def ensure_data_dir(path: Path = DEFAULT_LEDGER_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def add_clv_columns(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    cleaned = update_profit_columns(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if cleaned.empty:
        return pd.DataFrame()
    rows = []
    for row in cleaned.to_dict(orient='records'):
        item = dict(row)
        locked_price = _safe_float(item.get('decimal_price'))
        closing_price = _safe_float(item.get('closing_decimal_price'))
        if locked_price is not None and closing_price is not None and locked_price > 1.0 and closing_price > 1.0:
            clv = (locked_price / closing_price) - 1.0
            item['clv_percent'] = round(clv, 6)
            item['beat_close'] = clv > 0
        else:
            item.setdefault('clv_percent', '')
            item.setdefault('beat_close', '')
        rows.append(item)
    return pd.DataFrame(rows)


def filter_locked_proof_rows(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    cleaned = add_clv_columns(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if cleaned.empty or not PROOF_REQUIRED_COLUMNS.issubset(set(cleaned.columns)):
        return pd.DataFrame()
    proof = cleaned['proof_id'].map(safe_text)
    locked_at = cleaned['locked_at_utc'].map(safe_text)
    return cleaned[proof.ne('') & locked_at.ne('')].copy()


def has_locked_proof_rows(frame: pd.DataFrame | list[dict[str, Any]]) -> bool:
    return not filter_locked_proof_rows(frame).empty


def _load_from_disk(workspace_id: Any = '', path: Path = DEFAULT_LEDGER_PATH) -> pd.DataFrame:
    ledger_path = persistent_ledger_path(workspace_id, path)
    try:
        if ledger_path.exists():
            return filter_locked_proof_rows(pd.read_csv(ledger_path))
    except Exception:
        return pd.DataFrame()
    return pd.DataFrame()


def _load_from_hold_store(workspace_id: Any = '') -> pd.DataFrame:
    rows = load_held_rows(LOCKED_STORE_KEY, workspace_id)
    if not rows:
        rows = load_held_rows(REFRESH_STORE_KEY, workspace_id)
    return filter_locked_proof_rows(rows)


def load_persistent_ledger(path: Path = DEFAULT_LEDGER_PATH, workspace_id: Any = '', active_only: bool = False) -> pd.DataFrame:
    disk = _load_from_disk(workspace_id, path)
    held = _load_from_hold_store(workspace_id)
    merged = merge_ledgers(disk, held)
    return latest_active_list(merged) if active_only else merged


def save_persistent_ledger(frame: pd.DataFrame | list[dict[str, Any]], path: Path = DEFAULT_LEDGER_PATH, workspace_id: Any = '') -> pd.DataFrame:
    ledger_path = persistent_ledger_path(workspace_id, path)
    cleaned = filter_locked_proof_rows(frame)
    if cleaned.empty:
        return pd.DataFrame()
    save_held_rows(LOCKED_STORE_KEY, cleaned, workspace_id)
    save_held_rows(REFRESH_STORE_KEY, cleaned, workspace_id)
    try:
        ensure_data_dir(ledger_path)
        cleaned.to_csv(ledger_path, index=False)
    except Exception:
        pass
    return cleaned


def merge_ledgers(*frames: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    usable = []
    for frame in frames:
        raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
        locked = filter_locked_proof_rows(raw) if raw is not None and not raw.empty else pd.DataFrame()
        if not locked.empty:
            usable.append(locked)
    if not usable:
        return pd.DataFrame()
    merged = pd.concat(usable, ignore_index=True, sort=False)
    if 'proof_id' in merged.columns:
        proof = merged['proof_id'].map(safe_text)
        with_proof = merged[proof.ne('')].drop_duplicates(subset=['proof_id'], keep='last')
        without_proof = merged[proof.eq('')]
        merged = pd.concat([with_proof, without_proof], ignore_index=True, sort=False)
    fallback_cols = [col for col in ['event', 'prediction', 'event_start_utc', 'market_type'] if col in merged.columns]
    if fallback_cols:
        merged = merged.drop_duplicates(subset=fallback_cols, keep='last')
    return filter_locked_proof_rows(merged)


def latest_active_list(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    """Return only the newest proof list for headline dashboard metrics.

    Workspaces can hold more than one locked list while testing. The headline record must not blend old trackers
    with the newest list, so rows are grouped by list_id/ledger_batch_id/source_file/locked_at_utc and the newest
    group is used.
    """
    locked = filter_locked_proof_rows(frame)
    if locked.empty:
        return pd.DataFrame()
    out = locked.copy()
    if 'active_list_id' in out.columns:
        values = [safe_text(v) for v in out['active_list_id']]
        nonempty = [v for v in values if v]
        if nonempty:
            active = nonempty[-1]
            selected = out[out['active_list_id'].map(safe_text).eq(active)].copy()
            if not selected.empty:
                return selected
    for col in ['ledger_batch_id', 'list_id', 'source_file']:
        if col in out.columns:
            labels = out[col].map(safe_text)
            nonempty = labels[labels.ne('')]
            if not nonempty.empty:
                last_label = nonempty.iloc[-1]
                selected = out[labels.eq(last_label)].copy()
                if not selected.empty:
                    return selected
    if 'locked_at_utc' in out.columns:
        parsed = pd.to_datetime(out['locked_at_utc'], errors='coerce', utc=True)
        if parsed.notna().any():
            newest = parsed.max()
            selected = out[parsed.eq(newest)].copy()
            if not selected.empty:
                return selected
    return out


def _key_text(value: Any) -> str:
    return ' '.join(str(value or '').lower().replace('-', ' ').replace('_', ' ').split())


def _match_key(row: Mapping[str, Any]) -> str:
    return '|'.join([
        _key_text(row.get('event')),
        _key_text(row.get('prediction')),
        _key_text(row.get('market_type')),
        _key_text(row.get('event_start_utc')),
    ])


def _result_from_row(row: Mapping[str, Any], pick: str = '') -> str:
    status = result_status(row)
    if status in {'win', 'loss', 'void'}:
        return status
    winner = _key_text(row.get('winner') or row.get('actual_winner') or row.get('final_winner'))
    if winner and pick:
        return 'win' if winner == _key_text(pick) else 'loss'
    return status if status else 'pending'


def apply_result_updates(ledger: pd.DataFrame | list[dict[str, Any]], results: pd.DataFrame | list[dict[str, Any]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    locked = filter_locked_proof_rows(ledger)
    result_frame = normalize_frame(pd.DataFrame(results) if isinstance(results, list) else results)
    if locked.empty:
        return pd.DataFrame(), {'updated_rows': 0, 'matched_by_proof_id': 0, 'matched_by_event_pick': 0, 'unmatched_results': int(len(result_frame)) if result_frame is not None else 0}
    if result_frame.empty:
        return filter_locked_proof_rows(locked), {'updated_rows': 0, 'matched_by_proof_id': 0, 'matched_by_event_pick': 0, 'unmatched_results': 0}

    proof_lookup: dict[str, Mapping[str, Any]] = {}
    key_lookup: dict[str, Mapping[str, Any]] = {}
    for row in result_frame.to_dict(orient='records'):
        proof_id = safe_text(row.get('proof_id'))
        if proof_id:
            proof_lookup[proof_id] = row
        key = _match_key(row)
        if key.strip('|'):
            key_lookup[key] = row

    rows = []
    updated = 0
    proof_matches = 0
    key_matches = 0
    matched_result_keys: set[str] = set()
    for row in locked.to_dict(orient='records'):
        item = dict(row)
        match = None
        proof_id = safe_text(item.get('proof_id'))
        if proof_id and proof_id in proof_lookup:
            match = proof_lookup[proof_id]
            proof_matches += 1
            matched_result_keys.add(f'proof:{proof_id}')
        else:
            key = _match_key(item)
            if key in key_lookup:
                match = key_lookup[key]
                key_matches += 1
                matched_result_keys.add(f'key:{key}')
        if match is not None:
            result = _result_from_row(match, pick=safe_text(item.get('prediction')))
            if result in {'win', 'loss', 'void'}:
                item['result_status'] = result
                item['winner'] = safe_text(match.get('winner') or match.get('actual_winner') or match.get('final_winner') or item.get('winner'))
                item['final_score'] = safe_text(match.get('final_score') or match.get('score') or item.get('final_score'))
                closing = safe_text(match.get('closing_decimal_price') or match.get('closing_price') or match.get('close_decimal') or match.get('closing_odds'))
                if closing:
                    item['closing_decimal_price'] = closing
                item['graded_at_utc'] = pd.Timestamp.utcnow().isoformat()
                updated += 1
        rows.append(item)
    updated_frame = filter_locked_proof_rows(pd.DataFrame(rows))
    unmatched = max(0, len(result_frame) - len(matched_result_keys))
    return updated_frame, {'updated_rows': updated, 'matched_by_proof_id': proof_matches, 'matched_by_event_pick': key_matches, 'unmatched_results': unmatched}
