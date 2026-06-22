from __future__ import annotations

from typing import Any

import pandas as pd

from .commercial_platform_tools import filter_locked_proof_rows, load_persistent_ledger, merge_ledgers, save_persistent_ledger
from .pick_hold_store import save_held_rows
from .row_normalizer import safe_text

SESSION_LEDGER_KEYS = ('odds_lock_pro_locked_rows', 'public_proof_dashboard_refresh_rows')


def _active_label(frame: pd.DataFrame) -> str:
    if frame is None or frame.empty:
        return ''
    for col in ('active_list_id', 'ledger_batch_id', 'list_id', 'source_file'):
        if col in frame.columns:
            values = frame[col].map(safe_text)
            nonempty = values[values.ne('')]
            if not nonempty.empty:
                return f'{col}:{nonempty.iloc[-1]}'
    if 'locked_at_utc' in frame.columns:
        parsed = pd.to_datetime(frame['locked_at_utc'], errors='coerce', utc=True)
        if parsed.notna().any():
            return 'locked_at_utc:' + parsed.max().isoformat()
    return ''


def _drop_same_active_list(history: pd.DataFrame, active: pd.DataFrame) -> pd.DataFrame:
    if history.empty or active.empty:
        return history
    label = _active_label(active)
    if not label:
        return history
    col, _, value = label.partition(':')
    if col in history.columns:
        return history[~history[col].map(safe_text).eq(value)].copy()
    return history


def sync_dashboard_state(frame: pd.DataFrame | list[dict[str, Any]], workspace_id: Any = '') -> pd.DataFrame:
    active = filter_locked_proof_rows(frame)
    if active.empty:
        return pd.DataFrame()
    history = load_persistent_ledger(workspace_id=workspace_id, active_only=False)
    history = _drop_same_active_list(history, active)
    combined = merge_ledgers(history, active, active_only=False)
    saved_all = save_persistent_ledger(combined, workspace_id=workspace_id)
    active_rows = active.to_dict(orient='records')
    # Session/dashboard keys should receive only the active list; persistent storage keeps all lists for learning.
    for key in SESSION_LEDGER_KEYS:
        save_held_rows(key, active_rows, workspace_id)
    try:
        import streamlit as st
        for key in SESSION_LEDGER_KEYS:
            st.session_state[key] = active_rows
    except Exception:
        pass
    return active
