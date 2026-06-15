from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.clv import build_clv_frame, clv_summary
from autonomous_betting_agent.local_users import current_user_from_session
from autonomous_betting_agent.proof_ledger import load_ledger

st.set_page_config(page_title='CLV Tracker', layout='wide')
st.title('Closing-Line Value Tracker')
st.caption('Compares locked prediction odds against closing odds. Positive CLV is useful evidence even before all games finish.')

profile = current_user_from_session(st.session_state)
source = st.radio('Data source', ['Proof ledger / uploaded closing columns', 'Upload CSV'], horizontal=True)

if source.startswith('Proof'):
    frame = load_ledger(profile.user_id)
else:
    upload = st.file_uploader('Upload CSV with locked and closing odds', type=['csv'])
    pasted = st.text_area('Or paste CSV text', height=120)
    if upload is not None:
        frame = pd.read_csv(upload)
    elif pasted.strip():
        frame = pd.read_csv(StringIO(pasted.strip()))
    else:
        frame = pd.DataFrame()

if frame.empty:
    st.warning('No rows found. Add a CSV with decimal_price and closing_decimal_price columns.')
    st.stop()

clv = build_clv_frame(frame)
summary = clv_summary(frame)
cols = st.columns(5)
cols[0].metric('Rows', summary['rows'])
cols[1].metric('With CLV', summary['with_clv'])
cols[2].metric('Positive CLV', summary['positive_clv'])
cols[3].metric('Positive CLV rate', '' if summary['positive_clv_rate'] is None else f"{summary['positive_clv_rate']:.1%}")
cols[4].metric('Avg CLV edge', '' if summary['avg_clv_probability_edge'] is None else f"{summary['avg_clv_probability_edge']:.2%}")

st.subheader('CLV records')
st.dataframe(clv, use_container_width=True, hide_index=True)
st.download_button('Download CLV CSV', clv.to_csv(index=False), file_name=f'{profile.user_id}_clv_tracker.csv', mime='text/csv')

with st.expander('How to use this', expanded=False):
    st.write('Add a closing_decimal_price or closing_price column after the market closes. If the model locked a better implied probability than the closing market, the row gets positive CLV.')
