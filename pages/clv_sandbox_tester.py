from __future__ import annotations

import io
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='CLV Sandbox Tester', layout='wide')
render_app_sidebar('clv_sandbox_tester', selector='radio')

st.title('CLV Sandbox Tester')
st.caption('Sandbox-only calculator. This page does not read, write, or modify the proof ledger.')
st.info('Use this page to verify Avg CLV and Beat Close without touching the Public Proof Dashboard, win/loss grading, ROI, units, or proof IDs.')


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _first_numeric(frame: pd.DataFrame, fields: list[str]) -> pd.Series:
    out = pd.Series(float('nan'), index=frame.index, dtype='float64')
    for field in fields:
        if field in frame.columns:
            values = pd.to_numeric(frame[field], errors='coerce')
            out = out.where(out.notna(), values)
    return out


def calculate_clv(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    if frame.empty:
        return pd.DataFrame(), {'rows': 0, 'avg_clv_percent': None, 'beat_close_rate': None, 'clv_sample_size': 0, 'beat_close_sample_size': 0}
    out = frame.copy()
    locked = _first_numeric(out, ['locked_decimal_price', 'lock_decimal_price', 'decimal_price', 'locked_price'])
    closing = _first_numeric(out, ['closing_decimal_price', 'close_decimal_price', 'closing_price', 'market_close_decimal_price', 'final_decimal_price'])
    explicit_clv = _first_numeric(out, ['clv_percent', 'closing_line_value_percent', 'clv'])
    computed_clv = (locked / closing) - 1.0
    clv = explicit_clv.where(explicit_clv.notna(), computed_clv)
    clv = clv.where(clv.abs().le(1.0), clv / 100.0)
    beat_close = locked.gt(closing).where(locked.notna() & closing.notna())
    out['locked_price_used'] = locked
    out['closing_price_used'] = closing
    out['clv_percent_computed'] = clv
    out['beat_close_computed'] = beat_close
    clv_clean = clv.dropna()
    beat_clean = beat_close.dropna()
    metrics = {
        'rows': int(len(out)),
        'avg_clv_percent': None if clv_clean.empty else round(float(clv_clean.mean()), 6),
        'beat_close_rate': None if beat_clean.empty else round(float(beat_clean.astype(bool).mean()), 6),
        'clv_sample_size': int(len(clv_clean)),
        'beat_close_sample_size': int(len(beat_clean)),
    }
    return out, metrics


def pct(value: float | None, digits: int = 2) -> str:
    return 'N/A' if value is None else f'{value * 100:.{digits}f}%'

st.subheader('Manual quick test')
left, right = st.columns(2)
locked_price = left.number_input('Locked decimal price', min_value=1.01, max_value=100.0, value=2.10, step=0.01)
closing_price = right.number_input('Closing decimal price', min_value=1.01, max_value=100.0, value=2.00, step=0.01)
manual = pd.DataFrame([{'decimal_price': locked_price, 'closing_decimal_price': closing_price}])
manual_out, manual_metrics = calculate_clv(manual)
mc = st.columns(4)
mc[0].metric('Manual CLV', pct(manual_metrics['avg_clv_percent']))
mc[1].metric('Manual Beat Close', pct(manual_metrics['beat_close_rate']))
mc[2].metric('Locked', locked_price)
mc[3].metric('Closing', closing_price)

st.divider()
st.subheader('CSV paste sandbox')
st.caption('Paste CSV rows here. No button is required; the page recalculates automatically when text is present.')
default_csv = 'proof_id,decimal_price,closing_decimal_price\nTEST-1,2.10,2.00\nTEST-2,1.80,1.90\nTEST-3,1.60,1.55\n'
csv_text = st.text_area('Sandbox CSV text', value=default_csv, height=150)
try:
    pasted = pd.read_csv(io.StringIO(csv_text.strip())) if csv_text.strip() else pd.DataFrame()
except Exception as exc:
    st.error(f'CSV parse error: {exc}')
    st.stop()
calc, metrics = calculate_clv(pasted)
cols = st.columns(5)
cols[0].metric('Rows', metrics['rows'])
cols[1].metric('Avg CLV', pct(metrics['avg_clv_percent']))
cols[2].metric('Beat Close', pct(metrics['beat_close_rate']))
cols[3].metric('CLV sample', metrics['clv_sample_size'])
cols[4].metric('Beat sample', metrics['beat_close_sample_size'])
st.dataframe(calc, use_container_width=True, hide_index=True)
st.download_button('Download sandbox CLV output CSV', calc.to_csv(index=False), file_name='clv_sandbox_output.csv', mime='text/csv')

st.warning('This page is isolated. It does not save results to the real ledger.')
