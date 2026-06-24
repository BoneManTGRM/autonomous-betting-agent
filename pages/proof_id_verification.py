from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.explanations import build_client_safe_pick_summary
from autonomous_betting_agent.ledger_types import classify_ledger_type, is_future_locked, public_metric_allowed
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.storage import LocalStorage

st.set_page_config(page_title="Proof ID Verification", layout="wide")
render_app_sidebar("proof_id_verification", language_key="proof_id_verification_language")

st.title("Proof ID Verification")
st.caption("Search local proof rows by proof ID and verify lock time, event start, ledger type, grade, and public-safe status.")

store = LocalStorage()
rows = store.load_rows()

proof_id = st.text_input("Proof ID", "").strip()

if not proof_id:
    st.info("Enter a proof ID to verify a local row.")
    st.stop()

matches = [row for row in rows if str(row.get("proof_id") or "").strip() == proof_id]
if not matches:
    st.error("No local row found for that proof ID.")
    st.stop()

row = matches[0]
ledger_type = classify_ledger_type(row)
future_locked = is_future_locked(row)
public_safe = public_metric_allowed(row)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Ledger type", ledger_type)
col2.metric("Forward locked", "Yes" if future_locked else "No")
col3.metric("Public-safe", "Yes" if public_safe else "No")
col4.metric("Grade", str(row.get("grade") or row.get("result") or "pending"))

st.subheader("Verification fields")
st.write({
    "proof_id": row.get("proof_id"),
    "proof_hash": row.get("proof_hash"),
    "locked_at_utc": row.get("locked_at_utc"),
    "event_start_time": row.get("event_start_time") or row.get("commence_time"),
    "event_name": row.get("event_name") or row.get("event") or row.get("matchup"),
    "prediction": row.get("prediction") or row.get("pick") or row.get("selection"),
    "market": row.get("market") or row.get("market_type"),
    "odds_audit_status": row.get("odds_audit_status") or row.get("audit_status"),
})

st.subheader("Client-safe explanation")
st.info(build_client_safe_pick_summary(row))

with st.expander("Full local row"):
    st.dataframe(pd.DataFrame([row]), use_container_width=True)

st.warning("Verification confirms local proof fields only. It does not guarantee outcomes or returns.")
