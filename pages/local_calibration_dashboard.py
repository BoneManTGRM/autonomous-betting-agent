from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.local_calibration import brier_score, calibration_buckets, odds_band_summary
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.storage import LocalStorage

st.set_page_config(page_title="Local Calibration Dashboard", layout="wide")
render_app_sidebar("local_calibration_dashboard", language_key="local_calibration_dashboard_language")
require_streamlit_access(st, allow_roles={"admin"})

st.title("Local Calibration Dashboard")
st.caption("Review probability calibration from local graded rows. No cloud server required.")

store = LocalStorage()
rows = store.load_rows()
if not rows:
    st.info("No local rows found yet.")
    st.stop()

ledger = st.selectbox("Ledger", ["all", "official", "client", "research", "all_high_confidence", "quarantine", "learning_only"])
visible = rows if ledger == "all" else store.load_rows(ledger)
resolved = [row for row in visible if str(row.get("grade") or row.get("result") or "").strip().lower() in {"win", "won", "w", "loss", "lost", "l"}]

col1, col2, col3 = st.columns(3)
col1.metric("Rows in view", len(visible))
col2.metric("Resolved win/loss rows", len(resolved))
score = brier_score(resolved)
col3.metric("Brier score", "N/A" if score is None else f"{score:.4f}")

st.subheader("Confidence bucket calibration")
buckets = calibration_buckets(resolved)
if buckets:
    bucket_df = pd.DataFrame(buckets)
    st.dataframe(bucket_df, use_container_width=True)
    st.bar_chart(bucket_df.set_index("bucket")[["expected_win_rate", "actual_win_rate"]])
else:
    st.info("No graded rows with usable probabilities were found.")

st.subheader("Odds band performance")
odds_df = pd.DataFrame(odds_band_summary(resolved))
st.dataframe(odds_df, use_container_width=True)

st.warning("Calibration is a diagnostic tool only. It does not guarantee future outcomes or returns.")
