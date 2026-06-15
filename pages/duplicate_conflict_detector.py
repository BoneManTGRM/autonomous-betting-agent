from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.duplicate_conflicts import build_duplicate_conflict_frame, duplicate_conflict_summary

st.set_page_config(page_title='Duplicate Conflict Detector', layout='wide')
st.title('Duplicate Conflict Detector')
st.caption('Find exact duplicates, repeated picks, conflicting predictions, conflicting results, and price variants.')

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
    st.warning('Upload or paste a CSV to inspect duplicates and conflicts.')
    st.stop()

checked = build_duplicate_conflict_frame(raw)
summary = duplicate_conflict_summary(raw)

st.info(f'Source: {source_label} | Rows: {summary["rows"]}')
cols = st.columns(7)
cols[0].metric('Clean', summary['clean'])
cols[1].metric('Exact dupes', summary['exact_duplicates'])
cols[2].metric('Pick variants', summary['same_pick_variants'])
cols[3].metric('Prediction conflicts', summary['prediction_conflicts'])
cols[4].metric('Result conflicts', summary['result_conflicts'])
cols[5].metric('Price conflicts', summary['price_conflicts'])
cols[6].metric('Rows', summary['rows'])

problem_rows = checked[checked['duplicate_type'].ne('clean')].copy() if 'duplicate_type' in checked.columns else pd.DataFrame()
if problem_rows.empty:
    st.success('No duplicate or conflict problems detected.')
else:
    st.warning(f'{len(problem_rows)} rows need review.')

st.subheader('Problem rows')
st.dataframe(problem_rows.head(300), use_container_width=True, hide_index=True)
st.subheader('All checked rows')
st.dataframe(checked.head(300), use_container_width=True, hide_index=True)

st.download_button('Download duplicate conflict report CSV', checked.to_csv(index=False), file_name='duplicate_conflict_report.csv', mime='text/csv')
if not problem_rows.empty:
    st.download_button('Download problem rows CSV', problem_rows.to_csv(index=False), file_name='duplicate_conflict_problem_rows.csv', mime='text/csv')
