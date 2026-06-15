from __future__ import annotations

from io import StringIO
import json
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from autonomous_betting_agent.daily_report import build_daily_report, daily_report_markdown
from autonomous_betting_agent.review_packet import build_review_packet, packet_markdown
from autonomous_betting_agent.row_normalizer import normalize_frame

st.set_page_config(page_title='Review Bundle Export', layout='wide')
st.title('Review Bundle Export')
st.caption('Creates a compact package with review summary, daily report, JSON exports, and normalized CSV.')

report_date = st.date_input('Report date', value=datetime.now(timezone.utc).date())
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
    st.warning('Upload or paste a CSV to build the review bundle.')
    st.stop()

normalized = normalize_frame(raw)
review_packet = build_review_packet(normalized, starting_units=float(starting_units))
daily_packet = build_daily_report(normalized, report_date=report_date.isoformat(), starting_units=float(starting_units))
review_md = packet_markdown(review_packet)
daily_md = daily_report_markdown(daily_packet)
combined_md = review_md + '\n---\n\n' + daily_md
combined_json = {'review_packet': review_packet, 'daily_operations_report': daily_packet}

st.info(f'Source: {source_label} | Rows: {len(normalized)}')
cols = st.columns(6)
cols[0].metric('Quality Score', f"{review_packet['quality']['quality_score']}/100")
cols[1].metric('Rows', review_packet['rows'])
cols[2].metric('Wins', review_packet['statistics']['wins'])
cols[3].metric('Losses', review_packet['statistics']['losses'])
cols[4].metric('Resolved', review_packet['statistics']['total'])
cols[5].metric('Daily Net Units', daily_packet['bankroll']['net_units'])

tab_review, tab_daily, tab_json, tab_data = st.tabs(['Review Summary', 'Daily Report', 'JSON', 'Normalized CSV'])
with tab_review:
    st.markdown(review_md)
with tab_daily:
    st.markdown(daily_md)
with tab_json:
    st.json(combined_json)
with tab_data:
    st.dataframe(normalized.head(500), use_container_width=True, hide_index=True)

st.download_button('Download combined review bundle Markdown', combined_md, file_name='review_bundle.md', mime='text/markdown')
st.download_button('Download combined review bundle JSON', json.dumps(combined_json, indent=2, default=str), file_name='review_bundle.json', mime='application/json')
st.download_button('Download normalized review CSV', normalized.to_csv(index=False), file_name='review_bundle_normalized.csv', mime='text/csv')
