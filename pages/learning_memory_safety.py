from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.learning_memory_controls import reset_confirmation_matches, split_learning_safe_rows, version_placeholder_path
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

safe_rows, blocked_rows = split_learning_safe_rows(rows)

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

st.subheader("Import preview only")
upload = st.file_uploader("Preview a learning-safe CSV before using it elsewhere", type=["csv"])
if upload is not None:
    try:
        preview = pd.read_csv(upload)
        st.dataframe(preview.head(100), use_container_width=True)
        st.caption("Preview only. This page does not automatically train, overwrite, or reset memory.")
    except Exception as exc:
        st.warning(f"Could not preview CSV: {exc}")

st.subheader("Version and reset controls")
version_label = st.text_input("Version label placeholder", "manual")
st.code(str(version_placeholder_path(version_label)))
st.caption("Use this path as a future local version marker before replacing memory files. This page does not write the version file automatically.")
confirmation = st.text_input("Reset confirmation placeholder", "", help="Type RESET LEARNING MEMORY to enable the placeholder warning.")
if reset_confirmation_matches(confirmation):
    st.error("Reset confirmation entered. This page still does not delete memory automatically; back up files before any manual reset.")
else:
    st.info("Reset disabled. Exact confirmation is required before any future reset workflow should run.")

st.subheader("Before/after and pattern review placeholders")
st.write({
    "before_after_comparison": "Placeholder: compare performance before and after a memory update.",
    "patterns_improved": "Placeholder: list pattern groups that improved after learning.",
    "patterns_failed": "Placeholder: list pattern groups that weakened or should be excluded.",
})

st.subheader("Blocked or review rows")
if blocked_rows:
    st.dataframe(pd.DataFrame(blocked_rows), use_container_width=True)
else:
    st.success("No blocked rows in the current local set.")

st.warning("Do not train Learning Memory on quarantined, ungraded, result-only, missing-probability, or bad-price rows.")
