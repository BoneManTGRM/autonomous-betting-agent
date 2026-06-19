from __future__ import annotations

from typing import Any

import pandas as pd

from .commercial_platform_tools import load_persistent_ledger, merge_ledgers, normalize_workspace_id, save_persistent_ledger
from .odds_lock_tools import lock_status, now_utc, proof_hash, proof_id_from_hash


def _float_or_blank(value: Any) -> Any:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return ''
    if pd.isna(parsed) or parsed <= 0:
        return ''
    return parsed


def _probability(value: Any) -> Any:
    parsed = _float_or_blank(value)
    if parsed == '':
        return ''
    return round(parsed / 100.0 if parsed > 1 else parsed, 6)


def _make_row(st: Any, *, prefix: str, source: str) -> dict[str, Any] | None:
    event = str(st.session_state.get(prefix + '_event') or '').strip()
    pick = str(st.session_state.get(prefix + '_pick') or '').strip()
    if not event or not pick:
        return None
    workspace_id = normalize_workspace_id(st.session_state.get('aba_test_window_id') or 'test_01')
    locked_at = now_utc()
    row = {
        'event': event,
        'sport': str(st.session_state.get(prefix + '_sport') or '').strip() or 'manual_entry',
        'market_type': str(st.session_state.get(prefix + '_market') or 'h2h'),
        'prediction': pick,
        'event_start_utc': str(st.session_state.get(prefix + '_start') or '').strip(),
        'model_probability': _probability(st.session_state.get(prefix + '_prob')),
        'decimal_price': _float_or_blank(st.session_state.get(prefix + '_price')),
        'bookmaker': str(st.session_state.get(prefix + '_book') or '').strip() or 'manual_entry',
        'odds_source': str(st.session_state.get(prefix + '_book') or '').strip() or 'manual_entry',
        'manual_context_notes': str(st.session_state.get(prefix + '_notes') or '').strip(),
        'locked_at_utc': locked_at,
        'test_window_id': workspace_id,
        'ledger_type': source,
        'official_ev_pick': False,
        'agent_decision': source,
        'stake_units': 1.0,
        'result_status': 'pending',
        'public_confidence': 'Manual Hold',
        'public_reason': 'Manually held research pick. Not official +EV proof unless completed before start with full odds/probability fields.',
        'lock_blockers': '',
    }
    row['proof_status'] = lock_status(row)
    row['proof_hash'] = proof_hash(row)
    row['proof_id'] = proof_id_from_hash(row['proof_hash'])
    return row


def _save_row(st: Any, row: dict[str, Any], *, signature: str) -> None:
    last_key = '_aba_last_manual_hold_signature'
    if st.session_state.get(last_key) == signature:
        st.info('Already saved this exact pick. Change the game or pick to save another one.')
        return
    workspace_id = normalize_workspace_id(st.session_state.get('aba_test_window_id') or 'test_01')
    existing = load_persistent_ledger(workspace_id=workspace_id)
    saved = save_persistent_ledger(merge_ledgers(existing, pd.DataFrame([row])), workspace_id=workspace_id)
    records = saved.to_dict('records')
    st.session_state['odds_lock_pro_locked_rows'] = records
    st.session_state['public_proof_dashboard_refresh_rows'] = records
    st.session_state['ara_latest_predictions'] = records
    st.session_state[last_key] = signature
    st.success(f'Pick held and saved to {workspace_id}. Rows saved: {len(records)}')


def _render_buttonless_hold(st: Any, *, prefix: str, expanded: bool, source: str) -> None:
    if st.session_state.get(prefix + '_rendered'):
        return
    st.session_state[prefix + '_rendered'] = True
    with st.expander('No-button pick hold / Guardar pick sin botón', expanded=expanded):
        st.caption('If app buttons are not firing on mobile, use this. Fill the fields, then type SAVE in the last box and press return. It saves directly to the active test ledger.')
        c1, c2 = st.columns(2)
        c1.text_input('Game / event', key=prefix + '_event')
        c2.text_input('Pick / prediction', key=prefix + '_pick')
        c3, c4, c5 = st.columns(3)
        c3.text_input('Sport / league', key=prefix + '_sport')
        c4.selectbox('Market', ['h2h', 'spreads', 'totals', 'prop', 'other'], key=prefix + '_market')
        c5.text_input('Event start UTC', key=prefix + '_start')
        c6, c7, c8 = st.columns(3)
        c6.number_input('Model probability %', min_value=0.0, max_value=100.0, value=0.0, step=0.5, key=prefix + '_prob')
        c7.number_input('Decimal odds', min_value=0.0, max_value=1000.0, value=0.0, step=0.01, key=prefix + '_price')
        c8.text_input('Bookmaker/source', key=prefix + '_book')
        st.text_area('Notes', key=prefix + '_notes', height=80)
        trigger = st.text_input('Type SAVE here to hold this pick', key=prefix + '_save_trigger')
        if str(trigger or '').strip().upper() == 'SAVE':
            row = _make_row(st, prefix=prefix, source=source)
            if row is None:
                st.error('Enter at least the game/event and pick.')
                return
            signature = '|'.join([str(row.get('test_window_id')), str(row.get('event')).lower(), str(row.get('prediction')).lower(), str(row.get('event_start_utc'))])
            _save_row(st, row, signature=signature)


def install_direct_pick_lock_patch() -> None:
    try:
        import streamlit as st
    except Exception:
        return
    if getattr(st, '_aba_direct_pick_lock_patch_v3', False):
        return
    original_title = st.title

    def patched_title(body: Any, *args: Any, **kwargs: Any) -> Any:
        result = original_title(body, *args, **kwargs)
        title = str(body).strip().lower()
        if title == 'odds lock pro':
            _render_buttonless_hold(st, prefix='manual_hold', expanded=True, source='manual_direct_hold')
        elif title == 'what are the odds':
            _render_buttonless_hold(st, prefix='wato_hold', expanded=False, source='what_are_the_odds_manual_hold')
        return result

    st.title = patched_title
    st._aba_direct_pick_lock_patch_v3 = True
