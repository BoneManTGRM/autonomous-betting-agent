from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.local_users import current_user_from_session
from autonomous_betting_agent.prediction_snapshot import build_prediction_snapshots, snapshot_summary, verify_snapshots
from autonomous_betting_agent.row_normalizer import normalize_frame

st.set_page_config(page_title='Odds Lock', layout='wide')
st.title('Odds Lock / Prediction Snapshot')
st.caption('Creates a tamper-evident lock for new predictions. Use this before games start, not after results are known.')

profile = current_user_from_session(st.session_state)
st.info(f'Active local user: {profile.display_name} ({profile.user_id})')

upload = st.file_uploader('Upload prediction CSV to lock now', type=['csv'])
pasted = st.text_area('Or paste prediction CSV text', height=120)
frame = pd.DataFrame()
if upload is not None:
    frame = pd.read_csv(upload)
elif pasted.strip():
    frame = pd.read_csv(StringIO(pasted.strip()))

if frame.empty:
    st.warning('Upload predictions to create an odds-locked snapshot.')
    st.stop()

normalized = normalize_frame(frame)
with st.expander('Normalized input preview', expanded=False):
    st.dataframe(normalized.head(50), use_container_width=True, hide_index=True)

st.warning('Only lock rows here if these are current predictions before the event starts. Historical rows should be inspected in CSV Doctor or Proof Readiness instead.')
create_lock = st.checkbox('Create official lock timestamp now for rows missing a timestamp', value=True)

snapshots = build_prediction_snapshots(normalized, user_id=profile.user_id, allow_auto_lock=create_lock)
summary = snapshot_summary(snapshots)
verification = verify_snapshots(snapshots)

cols = st.columns(6)
cols[0].metric('Rows', summary['total'])
cols[1].metric('Official locked', summary['official_locked'])
cols[2].metric('New locks created', summary['new_locks_created'])
cols[3].metric('Not official', summary['not_official'])
cols[4].metric('Missing odds', summary['missing_odds'])
cols[5].metric('Missing probability', summary['missing_probability'])

if verification.valid:
    st.success(f'Snapshot hashes valid for {verification.rows_checked} rows.')
else:
    st.error(f'Snapshot hash problem: {verification.message}')

st.subheader('Snapshot records')
st.dataframe(snapshots, use_container_width=True, hide_index=True)
st.download_button('Download locked snapshot CSV', snapshots.to_csv(index=False), file_name=f'{profile.user_id}_prediction_snapshots.csv', mime='text/csv')

with st.expander('Official-pick rule', expanded=False):
    st.write('A row is official only if it has event, prediction, model_probability, decimal_price, and a lock timestamp. Missing odds/probability rows can still be reviewed, but should not be counted as official ROI proof.')
