from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.row_normalizer import normalize_frame

VERSION_COLUMNS = ['model_version', 'calibration_version', 'memory_version', 'api_bundle_version']

st.set_page_config(page_title='Model Version Tracker', layout='wide')
st.title('Model Version Tracker')
st.caption('Track which model, calibration, memory, and API bundle produced each row.')

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
    st.warning('Upload or paste a CSV to inspect model versions.')
    st.stop()

frame = normalize_frame(raw)
for col in VERSION_COLUMNS:
    if col not in frame.columns:
        frame[col] = 'missing'
    frame[col] = frame[col].fillna('').astype(str).str.strip().replace('', 'missing')

summary = frame.groupby(VERSION_COLUMNS, dropna=False).size().reset_index(name='rows').sort_values('rows', ascending=False)
missing = {col: int(frame[col].eq('missing').sum()) for col in VERSION_COLUMNS}

st.info(f'Source: {source_label} | Rows: {len(frame)}')
cols = st.columns(4)
for idx, col in enumerate(VERSION_COLUMNS):
    cols[idx].metric(f'Missing {col}', missing[col])

st.subheader('Version summary')
st.dataframe(summary, use_container_width=True, hide_index=True)

st.subheader('Rows with version columns')
st.dataframe(frame.head(200), use_container_width=True, hide_index=True)

st.download_button('Download version summary CSV', summary.to_csv(index=False), file_name='model_version_summary.csv', mime='text/csv')
st.download_button('Download rows with version columns CSV', frame.to_csv(index=False), file_name='rows_with_versions.csv', mime='text/csv')

st.warning('Best future export rule: include model_version, calibration_version, memory_version, and api_bundle_version on every generated row.')
