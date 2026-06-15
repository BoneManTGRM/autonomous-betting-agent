from __future__ import annotations

from io import StringIO
import json

import pandas as pd
import streamlit as st

from autonomous_betting_agent.data_intake_gate import gates_frame, intake_gate, recognized_counts_frame
from autonomous_betting_agent.row_normalizer import normalize_frame

st.set_page_config(page_title='Data Intake Gate', layout='wide')
st.title('Data Intake Gate')
st.caption('First stop for any new CSV. It tells you whether the file is ready for learning, stats, proof, ROI, CLV, and forward testing.')

upload = st.file_uploader('Upload CSV', type=['csv'])
pasted = st.text_area('Or paste CSV text', height=120)

if upload is not None:
    raw = pd.read_csv(upload)
    source_label = upload.name
elif pasted.strip():
    raw = pd.read_csv(StringIO(pasted.strip()))
    source_label = 'pasted_csv'
else:
    raw = pd.DataFrame()
    source_label = ''

if raw.empty:
    st.warning('Upload or paste a CSV to inspect readiness.')
    st.stop()

normalized = normalize_frame(raw)
report = intake_gate(raw)

st.info(f'Source: {source_label} | Rows: {report["rows"]} | Status: {report["overall_status"].upper()} | {report["summary"]}')

cols = st.columns(5)
cols[0].metric('Rows', report['rows'])
cols[1].metric('Ready Gates', sum(1 for gate in report['gates'] if gate['ready']))
cols[2].metric('Official Locked', report['lock_summary']['official_locked'])
cols[3].metric('Proof Score', f"{report['proof_summary']['proof_score']}/100")
cols[4].metric('Resolved', report['statistical_summary']['total'])

if report['blockers']:
    st.subheader('Blockers')
    for item in report['blockers']:
        st.error(item)

if report['warnings']:
    st.subheader('Warnings')
    for item in report['warnings']:
        st.warning(item)

if report['next_actions']:
    st.subheader('Next actions')
    for item in report['next_actions']:
        st.write(f'- {item}')

st.subheader('Readiness gates')
st.dataframe(gates_frame(report), use_container_width=True, hide_index=True)

st.subheader('Recognized field counts')
st.dataframe(recognized_counts_frame(report), use_container_width=True, hide_index=True)

with st.expander('Normalized input preview', expanded=False):
    st.dataframe(normalized.head(100), use_container_width=True, hide_index=True)

st.download_button('Download intake report JSON', json.dumps(report, indent=2, default=str), file_name='data_intake_report.json', mime='application/json')
st.download_button('Download normalized CSV', normalized.to_csv(index=False), file_name='normalized_input.csv', mime='text/csv')
