from __future__ import annotations

from io import StringIO
import json

import pandas as pd
import streamlit as st

from autonomous_betting_agent.bankroll_tracker import build_bankroll_frame
from autonomous_betting_agent.duplicate_conflicts import build_duplicate_conflict_frame
from autonomous_betting_agent.line_movement import build_line_movement_frame
from autonomous_betting_agent.quality_control import build_quality_control_report
from autonomous_betting_agent.result_grader import grade_frame
from autonomous_betting_agent.row_normalizer import normalize_frame

st.set_page_config(page_title='Quality Control Center', layout='wide')
st.title('Quality Control Center')
st.caption('One place to check duplicates, conflicts, grading, line movement, bankroll path, and version coverage.')

starting_units = st.number_input('Starting units for bankroll path', min_value=1.0, max_value=100000.0, value=100.0, step=10.0)
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
    st.warning('Upload or paste a CSV to run quality control.')
    st.stop()

normalized = normalize_frame(raw)
report = build_quality_control_report(normalized, starting_units=float(starting_units))
duplicates = build_duplicate_conflict_frame(normalized)
graded = grade_frame(normalized)
movement = build_line_movement_frame(normalized)
bankroll = build_bankroll_frame(normalized, starting_units=float(starting_units))

st.info(f'Source: {source_label} | Rows: {report["rows"]}')
cols = st.columns(6)
cols[0].metric('Quality Score', f'{report["quality_score"]}/100')
cols[1].metric('Exact Duplicates', report['duplicates']['exact_duplicates'])
cols[2].metric('Conflicts', report['duplicates']['prediction_conflicts'] + report['duplicates']['result_conflicts'])
cols[3].metric('Review Needed', report['grading']['review_needed'])
cols[4].metric('Line Ready', report['line_movement']['ready'])
cols[5].metric('ROI %', 'N/A' if report['bankroll']['roi_percent'] is None else report['bankroll']['roi_percent'])

st.subheader('Recommendations')
for item in report['recommendations']:
    st.write(f'- {item}')

tab_summary, tab_duplicates, tab_grading, tab_line, tab_bankroll, tab_versions, tab_normalized = st.tabs([
    'Summary', 'Duplicates', 'Grading', 'Line Movement', 'Bankroll', 'Versions', 'Normalized Data'
])
with tab_summary:
    st.json(report)
with tab_duplicates:
    problem_rows = duplicates[duplicates['duplicate_type'].ne('clean')].copy() if not duplicates.empty and 'duplicate_type' in duplicates.columns else pd.DataFrame()
    st.subheader('Problem rows')
    st.dataframe(problem_rows.head(300), use_container_width=True, hide_index=True)
    st.subheader('All duplicate checks')
    st.dataframe(duplicates.head(300), use_container_width=True, hide_index=True)
with tab_grading:
    st.dataframe(graded.head(300), use_container_width=True, hide_index=True)
with tab_line:
    st.dataframe(movement.head(300), use_container_width=True, hide_index=True)
with tab_bankroll:
    if not bankroll.empty and 'sequence' in bankroll.columns and 'bankroll_units' in bankroll.columns:
        st.line_chart(bankroll.set_index('sequence')['bankroll_units'])
    st.dataframe(bankroll.head(300), use_container_width=True, hide_index=True)
with tab_versions:
    version_rows = [{'field': key, 'covered_rows': value} for key, value in report['version_coverage'].items()]
    st.dataframe(pd.DataFrame(version_rows), use_container_width=True, hide_index=True)
with tab_normalized:
    st.dataframe(normalized.head(300), use_container_width=True, hide_index=True)

st.download_button('Download quality control report JSON', json.dumps(report, indent=2, default=str), file_name='quality_control_report.json', mime='application/json')
st.download_button('Download normalized CSV', normalized.to_csv(index=False), file_name='quality_control_normalized.csv', mime='text/csv')
st.download_button('Download duplicate checks CSV', duplicates.to_csv(index=False), file_name='quality_control_duplicates.csv', mime='text/csv')
st.download_button('Download graded rows CSV', graded.to_csv(index=False), file_name='quality_control_graded.csv', mime='text/csv')
