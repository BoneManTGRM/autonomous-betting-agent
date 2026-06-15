from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.data_health import data_health_frame, data_health_score
from autonomous_betting_agent.local_users import current_user_from_session
from autonomous_betting_agent.proof_ledger import (
    append_predictions_to_ledger,
    ledger_path,
    ledger_summary,
    load_ledger,
    sport_breakdown,
    verify_hash_chain,
)

st.set_page_config(page_title='Proof Ledger', layout='wide')
st.title('Proof Ledger')
st.caption('Timestamped, tamper-evident local prediction ledger. This is the proof layer that turns CSV reports into an auditable record.')

profile = current_user_from_session(st.session_state)
st.info(f'Active local user: {profile.display_name} ({profile.user_id})')
st.caption(f'Ledger path: {ledger_path(profile.user_id)}')

ledger = load_ledger(profile.user_id)
verification = verify_hash_chain(ledger)
summary = ledger_summary(ledger)

cols = st.columns(6)
cols[0].metric('Total picks', summary['total_picks'])
cols[1].metric('Wins', summary['wins'])
cols[2].metric('Losses', summary['losses'])
cols[3].metric('Win rate', '' if summary['win_rate'] is None else f"{summary['win_rate']:.1%}")
cols[4].metric('Units', f"{summary['units']:.2f}")
cols[5].metric('ROI', '' if summary['roi_percent'] is None else f"{summary['roi_percent']:.2f}%")

if verification.valid:
    st.success(f'Hash chain valid. Rows checked: {verification.rows_checked}.')
else:
    st.error(f'Hash chain failed at row {verification.first_bad_row}: {verification.message}')

st.subheader('Append predictions to ledger')
st.caption('Upload or paste a prediction CSV. Rows are enriched, timestamped, assigned IDs, and chained with SHA-256 hashes.')
upload = st.file_uploader('Upload prediction CSV', type=['csv'])
pasted = st.text_area('Or paste CSV text', height=120)
input_frame = pd.DataFrame()
if upload is not None:
    input_frame = pd.read_csv(upload)
elif pasted.strip():
    input_frame = pd.read_csv(StringIO(pasted.strip()))

if not input_frame.empty:
    health = data_health_score(input_frame)
    hcols = st.columns(3)
    hcols[0].metric('Input rows', len(input_frame))
    hcols[1].metric('Data Health', f"{health['score']:.1f}/100")
    hcols[2].metric('Health Grade', health['grade'])
    with st.expander('Data health details', expanded=False):
        st.dataframe(data_health_frame(input_frame), use_container_width=True, hide_index=True)
    st.dataframe(input_frame.head(50), use_container_width=True, hide_index=True)
    if st.button('Append to proof ledger', type='primary'):
        updated = append_predictions_to_ledger(input_frame, user_id=profile.user_id, display_name=profile.display_name)
        st.success(f'Ledger updated. Total rows: {len(updated)}.')
        st.rerun()

st.subheader('Ledger records')
if ledger.empty:
    st.warning('No ledger rows yet. Add predictions above to start the proof record.')
else:
    with st.expander('Sport breakdown', expanded=True):
        st.dataframe(sport_breakdown(ledger), use_container_width=True, hide_index=True)
    st.dataframe(ledger.tail(250), use_container_width=True, hide_index=True)
    st.download_button('Download proof ledger CSV', ledger.to_csv(index=False), file_name=f'{profile.user_id}_prediction_ledger.csv', mime='text/csv')

with st.expander('Why this matters', expanded=False):
    st.write(
        {
            'proof': 'Every pick gets a prediction ID, timestamp, and row hash.',
            'tamper_evidence': 'Each row includes the previous row hash, creating a local hash chain.',
            'buyer_value': 'A buyer can inspect the record instead of relying on screenshots.',
            'limit': 'This is local proof, not a blockchain or third-party notarization yet.',
        }
    )
