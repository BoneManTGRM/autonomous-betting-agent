from __future__ import annotations

from io import StringIO
import json

import pandas as pd
import streamlit as st

from autonomous_betting_agent.readiness_scorecard import build_readiness_scorecard, checks_frame, next_actions_frame
from autonomous_betting_agent.row_normalizer import normalize_frame

st.set_page_config(page_title='Readiness Scorecard', layout='wide')
st.title('Readiness Scorecard')
st.caption('Scores whether the current data is ready for serious review based on quality, sample size, odds, units, line movement, versions, and segmentation.')

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
    st.warning('Upload or paste a CSV to build a readiness scorecard.')
    st.stop()

normalized = normalize_frame(raw)
scorecard = build_readiness_scorecard(normalized, starting_units=float(starting_units))

st.info(f'Source: {source_label} | Rows: {scorecard["rows"]} | Status: {scorecard["readiness_status"].upper()}')
cols = st.columns(6)
cols[0].metric('Readiness Score', f'{scorecard["readiness_score"]}/100')
cols[1].metric('Quality Score', f'{scorecard["quality_score"]}/100')
cols[2].metric('Resolved Rows', scorecard['resolved_rows'])
cols[3].metric('Net Units', scorecard['net_units'])
cols[4].metric('Observed Hit Rate', 'N/A' if scorecard['observed_hit_rate'] is None else f"{scorecard['observed_hit_rate']:.1%}")
cols[5].metric('95% Low', 'N/A' if scorecard['wilson_low_95'] is None else f"{scorecard['wilson_low_95']:.1%}")

st.subheader('Checks')
st.dataframe(checks_frame(scorecard), use_container_width=True, hide_index=True)

st.subheader('Next actions')
next_actions = next_actions_frame(scorecard)
if next_actions.empty:
    st.success('All readiness checks passed.')
else:
    st.dataframe(next_actions, use_container_width=True, hide_index=True)

with st.expander('Raw scorecard JSON', expanded=False):
    st.json(scorecard)

st.download_button('Download readiness scorecard JSON', json.dumps(scorecard, indent=2, default=str), file_name='readiness_scorecard.json', mime='application/json')
st.download_button('Download readiness checks CSV', checks_frame(scorecard).to_csv(index=False), file_name='readiness_checks.csv', mime='text/csv')
st.download_button('Download normalized CSV', normalized.to_csv(index=False), file_name='readiness_normalized.csv', mime='text/csv')
