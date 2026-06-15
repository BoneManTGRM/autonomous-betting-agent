from __future__ import annotations

from io import StringIO
import json

import pandas as pd
import streamlit as st

from autonomous_betting_agent.review_packet import build_review_packet, packet_markdown
from autonomous_betting_agent.row_normalizer import normalize_frame

st.set_page_config(page_title='Review Packet Export', layout='wide')
st.title('Review Packet Export')
st.caption('Creates a single review package with intake, quality, statistics, segments, scenarios, recommendations, and limitations.')

starting_units = st.number_input('Starting units', min_value=1.0, max_value=100000.0, value=100.0, step=10.0)
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
    st.warning('Upload or paste a CSV to build a review packet.')
    st.stop()

normalized = normalize_frame(raw)
packet = build_review_packet(normalized, starting_units=float(starting_units))
markdown = packet_markdown(packet)

st.info(f'Source: {source_label} | Rows: {packet["rows"]}')
cols = st.columns(5)
cols[0].metric('Rows', packet['rows'])
cols[1].metric('Quality Score', f"{packet['quality']['quality_score']}/100")
cols[2].metric('Wins', packet['statistics']['wins'])
cols[3].metric('Losses', packet['statistics']['losses'])
cols[4].metric('Resolved', packet['statistics']['total'])

st.subheader('Packet preview')
st.markdown(markdown)

with st.expander('Raw packet JSON', expanded=False):
    st.json(packet)

st.download_button('Download review packet Markdown', markdown, file_name='review_packet.md', mime='text/markdown')
st.download_button('Download review packet JSON', json.dumps(packet, indent=2, default=str), file_name='review_packet.json', mime='application/json')
st.download_button('Download normalized CSV', normalized.to_csv(index=False), file_name='review_packet_normalized.csv', mime='text/csv')
