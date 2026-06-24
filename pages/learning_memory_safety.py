from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.ledger_types import classify_ledger_type
from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.storage import LocalStorage

st.set_page_config(page_title="Learning Memory Safety", layout="wide")
render_app_sidebar("learning_memory_safety", language_key="learning_memory_safety_language")
require_streamlit_access(st, allow_roles={"admin"})

st.title("Learning Memory Safety")
st.caption("Review which local rows are safe for learning before training or updating memory.")

store = LocalStorage()
rows = store.load_rows()

if not rows:
    st.info("No local rows found yet.")
    st.stop()

safe_rows = []
blocked_rows = []
for row in rows:
    ledger_type = classify_ledger_type(row)
    grade = str(row.get("grade") or row.get("result") or "").strip().lower()
    audit_status = str(row.get("odds_audit_status") or row.get("audit_status") or "").strip().lower()
    has_probability = bool(row.get("learned_model_probability") or row.get("model_probability") or row.get("probability"))
    has_price = bool(row.get("decimal_price") or row.get("odds_at_pick"))
    usable_grade = grade in {"win", "won", "w", "loss", "lost", "l", "push", "void", "draw"}
    safe = ledger_type in {"official", "client", "research", "all_high_confidence"} and audit_status not in {"fail", "failed", "quarantine", "blocked"} and usable_grade and has_probability and has_price
    output = dict(row)
    output["learning_safe"] = safe
    output["learning_block_reason"] = "" if safe else "Needs grade, probability, proof-safe price, and non-quarantined audit status."
    output["ledger_type"] = ledger_type
    if safe:
        safe_rows.append(output)
    else:
        blocked_rows.append(output)

col1, col2, col3 = st.columns(3)
col1.metric("Total local rows", len(rows))
col2.metric("Learning-safe rows", len(safe_rows))
col3.metric("Blocked/review rows", len(blocked_rows))

st.subheader("Learning-safe rows")
if safe_rows:
    df = pd.DataFrame(safe_rows)
    st.dataframe(df, use_container_width=True)
    st.download_button("Download learning-safe CSV", df.to_csv(index=False).encode("utf-8"), file_name="learning_safe_rows.csv", mime="text/csv")
else:
    st.info("No rows currently meet the local learning-safety requirements.")

st.subheader("Blocked or review rows")
if blocked_rows:
    st.dataframe(pd.DataFrame(blocked_rows), use_container_width=True)
else:
    st.success("No blocked rows in the current local set.")

st.warning("Do not train Learning Memory on quarantined, ungraded, result-only, missing-probability, or bad-price rows.")
