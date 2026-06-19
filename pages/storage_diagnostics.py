from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.pick_hold_store import store_snapshot, normalize_workspace_id
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='Storage Diagnostics', layout='wide')
render_app_sidebar('storage_diagnostics')

st.title('Storage Diagnostics')
st.caption('Local session and disk recovery status for the active workspace.')

workspace_input = st.text_input('Workspace ID', value=st.session_state.get('aba_test_window_id', 'test_01'))
workspace_id = normalize_workspace_id(workspace_input)
st.session_state['aba_test_window_id'] = workspace_id

snapshot = store_snapshot(workspace_id)

st.metric('Active workspace', workspace_id)
st.metric('Total loaded rows', int(snapshot['loaded_rows'].sum()) if not snapshot.empty else 0)
st.metric('Total disk rows', int(snapshot['disk_rows'].sum()) if not snapshot.empty else 0)
st.metric('Total backup rows', int(snapshot['backup_rows'].sum()) if not snapshot.empty else 0)

st.dataframe(snapshot, use_container_width=True, hide_index=True)

if not snapshot.empty and snapshot['loaded_rows'].sum() == 0 and snapshot['disk_rows'].sum() == 0 and snapshot['backup_rows'].sum() == 0:
    st.warning('No saved local rows found for this workspace.')
elif not snapshot.empty:
    st.success('Local storage is readable for this workspace.')
