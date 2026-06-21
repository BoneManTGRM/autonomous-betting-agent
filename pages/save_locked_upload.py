from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import filter_locked_proof_rows, load_persistent_ledger, merge_ledgers, normalize_workspace_id, save_persistent_ledger
from autonomous_betting_agent.pick_hold_store import save_held_rows
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Save Locked Upload', layout='wide')
render_app_sidebar('save_locked_upload', language_key='save_locked_upload_language', selector='radio')

st.title('Save Locked Upload')
st.caption('For an already locked proof CSV. It saves valid proof rows directly to the active workspace.')

workspace_input = st.text_input('Workspace ID', value=st.session_state.get('aba_test_window_id', 'test_01'))
workspace_id = normalize_workspace_id(workspace_input)
st.session_state['aba_test_window_id'] = workspace_id

upload = st.file_uploader('Upload locked proof CSV', type=['csv'])
if upload is None:
    st.info('Upload the locked CSV here.')
    st.stop()

raw = pd.read_csv(upload)
locked = filter_locked_proof_rows(raw)
existing = load_persistent_ledger(workspace_id=workspace_id)
combined = merge_ledgers(existing, locked)

cols = st.columns(4)
cols[0].metric('Uploaded rows', len(raw))
cols[1].metric('Valid locked rows', len(locked))
cols[2].metric('Existing saved rows', len(existing))
cols[3].metric('After save total', len(combined))

if locked.empty:
    st.error('No valid locked rows found. The file needs proof_id and locked_at_utc.')
    st.dataframe(raw, use_container_width=True, hide_index=True)
    st.stop()

st.dataframe(locked, use_container_width=True, hide_index=True)

if st.button('Save uploaded locked rows to workspace', type='primary', use_container_width=True):
    saved = save_persistent_ledger(combined, workspace_id=workspace_id)
    records = saved.to_dict('records') if not saved.empty else []
    for key in ['odds_lock_pro_locked_rows', 'public_proof_dashboard_refresh_rows']:
        st.session_state[key] = records
        save_held_rows(key, records, workspace_id)
    st.success(f'Saved: {workspace_id} / {len(saved)} rows')
