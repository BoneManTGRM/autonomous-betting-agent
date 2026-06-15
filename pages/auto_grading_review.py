from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.grading_review import build_review_queue, review_summary
from autonomous_betting_agent.local_users import current_user_from_session
from autonomous_betting_agent.proof_ledger import load_ledger

st.set_page_config(page_title='Auto-Grading Review Center', layout='wide')
st.title('Auto-Grading Review Center')
st.caption('Separates pending, ready-to-grade, review-needed, void, duplicate, and clean graded rows.')

profile = current_user_from_session(st.session_state)
source = st.radio('Data source', ['Proof ledger', 'Upload CSV'], horizontal=True)

if source == 'Proof ledger':
    frame = load_ledger(profile.user_id)
else:
    upload = st.file_uploader('Upload CSV to review', type=['csv'])
    pasted = st.text_area('Or paste CSV text', height=120)
    if upload is not None:
        frame = pd.read_csv(upload)
    elif pasted.strip():
        frame = pd.read_csv(StringIO(pasted.strip()))
    else:
        frame = pd.DataFrame()

if frame.empty:
    st.warning('No rows found. Upload a CSV or add proof-ledger rows first.')
    st.stop()

queue = build_review_queue(frame)
summary = review_summary(queue)

st.subheader('Review summary')
st.dataframe(summary, use_container_width=True, hide_index=True)

status_filter = st.multiselect('Filter statuses', sorted(queue['review_status'].dropna().unique()), default=list(sorted(queue['review_status'].dropna().unique())))
filtered = queue[queue['review_status'].isin(status_filter)] if status_filter else queue

st.subheader('Review queue')
st.dataframe(filtered, use_container_width=True, hide_index=True)
st.download_button('Download review queue CSV', filtered.to_csv(index=False), file_name=f'{profile.user_id}_grading_review_queue.csv', mime='text/csv')
