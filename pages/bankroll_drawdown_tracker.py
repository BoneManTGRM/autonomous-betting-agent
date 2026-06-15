from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.bankroll_tracker import bankroll_summary, build_bankroll_frame

st.set_page_config(page_title='Bankroll Drawdown Tracker', layout='wide')
st.title('Bankroll Drawdown Tracker')
st.caption('Tracks unit balance, net units, ROI, drawdown, and streaks from stake_units and profit_units.')

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
    st.warning('Upload or paste a CSV with stake_units and profit_units.')
    st.stop()

tracked = build_bankroll_frame(raw, starting_units=float(starting_units))
summary = bankroll_summary(raw, starting_units=float(starting_units))

st.info(f'Source: {source_label} | Rows: {summary["rows"]}')
cols = st.columns(7)
cols[0].metric('Starting', summary['starting_units'])
cols[1].metric('Ending', summary['ending_units'])
cols[2].metric('Net units', summary['net_units'])
cols[3].metric('Total staked', summary.get('total_staked_units', 0))
cols[4].metric('ROI %', 'N/A' if summary['roi_percent'] is None else summary['roi_percent'])
cols[5].metric('Max drawdown', summary['max_drawdown_units'])
cols[6].metric('Worst streak', summary['longest_loss_streak'])

st.subheader('Bankroll path')
st.line_chart(tracked.set_index('sequence')['bankroll_units'] if not tracked.empty and 'sequence' in tracked.columns else tracked)

st.subheader('Tracked rows')
st.dataframe(tracked.head(300), use_container_width=True, hide_index=True)
st.download_button('Download bankroll tracker CSV', tracked.to_csv(index=False), file_name='bankroll_drawdown_report.csv', mime='text/csv')
