from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.line_movement import build_line_movement_frame, line_movement_summary

st.set_page_config(page_title='Line Movement Tracker', layout='wide')
st.title('Line Movement Tracker')
st.caption('Compares locked price to closing price and shows whether the market moved toward or away from the pick.')

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
    st.warning('Upload or paste a CSV with decimal_price and closing_decimal_price.')
    st.stop()

movement = build_line_movement_frame(raw)
summary = line_movement_summary(raw)

st.info(f'Source: {source_label} | Rows: {summary["rows"]}')
cols = st.columns(6)
cols[0].metric('Ready', summary['ready'])
cols[1].metric('Positive', summary['positive'])
cols[2].metric('Negative', summary['negative'])
cols[3].metric('Flat', summary['flat'])
cols[4].metric('Missing', summary['missing'])
cols[5].metric('Rows', summary['rows'])

st.subheader('Line movement rows')
st.dataframe(movement.head(300), use_container_width=True, hide_index=True)
st.download_button('Download line movement CSV', movement.to_csv(index=False), file_name='line_movement_report.csv', mime='text/csv')

st.warning('Positive movement usually means the locked price was better than the later closing price. This is useful market-signal evidence, not a guarantee of future results.')
