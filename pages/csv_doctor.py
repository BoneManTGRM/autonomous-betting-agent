from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.data_health import data_health_frame, data_health_score
from autonomous_betting_agent.prediction_snapshot import build_prediction_snapshots, snapshot_summary
from autonomous_betting_agent.proof_readiness import build_proof_readiness_frame, proof_readiness_summary
from autonomous_betting_agent.row_normalizer import ALIASES, normalize_frame

st.set_page_config(page_title='CSV Doctor', layout='wide')
st.title('CSV Doctor')
st.caption('Upload any prediction/results CSV and see what the app can understand before training, locking, grading, or reporting.')

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
    st.warning('Upload or paste a CSV to inspect it.')
    st.stop()

normalized = normalize_frame(raw)
health = data_health_score(normalized)
snapshots = build_prediction_snapshots(normalized)
locks = snapshot_summary(snapshots)
proof = build_proof_readiness_frame(normalized)
proof_summary = proof_readiness_summary(normalized)

st.info(f'Source: {source_label} | Rows: {len(raw)} | Columns: {len(raw.columns)}')
cols = st.columns(5)
cols[0].metric('Data Health', f"{health['score']:.0f}/100")
cols[1].metric('Official Locked', locks['official_locked'])
cols[2].metric('Not Official', locks['not_official'])
cols[3].metric('Proof Score', f"{proof_summary['proof_score']}/100")
cols[4].metric('Unusable/Unresolved', proof_summary['unresolved_or_unusable'])

st.subheader('Column mapping')
mapping_rows = []
raw_cols = {str(col).lower().replace(' ', '_').replace('-', '_'): col for col in raw.columns}
for canonical, aliases in ALIASES.items():
    matched = [raw_cols[alias] for alias in aliases if alias in raw_cols]
    mapping_rows.append({'standard_column': canonical, 'matched_input_columns': ', '.join(map(str, matched)), 'status': 'matched' if matched else 'missing'})
st.dataframe(pd.DataFrame(mapping_rows), use_container_width=True, hide_index=True)

st.subheader('Normalized preview')
st.dataframe(normalized.head(100), use_container_width=True, hide_index=True)

st.subheader('Data health details')
st.dataframe(data_health_frame(normalized), use_container_width=True, hide_index=True)

st.subheader('Official lock diagnosis')
st.dataframe(snapshots[['event', 'prediction', 'model_probability', 'decimal_price', 'locked_at_utc', 'lock_status', 'lock_reason']].head(100), use_container_width=True, hide_index=True)

st.subheader('Proof readiness diagnosis')
st.dataframe(proof[['event', 'prediction', 'result_status', 'model_probability', 'decimal_price', 'evidence_level', 'evidence_reason']].head(100), use_container_width=True, hide_index=True)

st.download_button('Download normalized CSV', normalized.to_csv(index=False), file_name='normalized_input.csv', mime='text/csv')
st.download_button('Download lock diagnosis CSV', snapshots.to_csv(index=False), file_name='lock_diagnosis.csv', mime='text/csv')
st.download_button('Download proof readiness CSV', proof.to_csv(index=False), file_name='proof_readiness_diagnosis.csv', mime='text/csv')
