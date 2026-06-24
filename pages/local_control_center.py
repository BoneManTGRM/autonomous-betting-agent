from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st

from autonomous_betting_agent.bankroll import suggest_stake
from autonomous_betting_agent.correlation import correlation_warnings
from autonomous_betting_agent.grading_rules import summarize_event_level, summarize_row_level
from autonomous_betting_agent.learning_memory_controls import reset_confirmation_matches, split_learning_safe_rows, version_placeholder_path
from autonomous_betting_agent.ledger_types import LEDGER_TYPES
from autonomous_betting_agent.license_status import load_license_records, make_license_record, upsert_license_record
from autonomous_betting_agent.local_access import require_streamlit_access
from autonomous_betting_agent.local_alerts import sqlite_fallback_alert
from autonomous_betting_agent.local_calibration import brier_score, calibration_buckets, odds_band_summary
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.storage import LocalStorage

st.set_page_config(page_title="Local Control Center", layout="wide")
render_app_sidebar("local_control_center", language_key="local_control_center_language")
require_streamlit_access(st, allow_roles={"admin"})

st.title("Local Control Center")
st.caption("Unified local storage, calibration, bankroll risk, license tracking, learning safety, and workflow guide.")
st.warning("Local Control Center is for analytics, proof tracking, reporting, and risk review only. It does not guarantee outcomes or returns.")

store = LocalStorage()
rows = store.load_rows()

if store.using_sqlite:
    st.success("Using local SQLite storage: data/aba_signal_pro.sqlite")
else:
    st.warning(sqlite_fallback_alert(store.sqlite_error)["message"])

ledger_counts = {ledger: len(store.load_rows(ledger)) for ledger in sorted(LEDGER_TYPES)}

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total local rows", len(rows))
col2.metric("Official rows", ledger_counts.get("official", 0))
col3.metric("Research rows", ledger_counts.get("research", 0))
col4.metric("Quarantine rows", ledger_counts.get("quarantine", 0))

tabs = st.tabs(["Storage/Admin", "Calibration", "Bankroll Risk", "License Tracking", "Learning Safety", "Workflow Guide", "Alerts/Status"])

with tabs[0]:
    st.subheader("Local storage/admin")
    st.dataframe(pd.DataFrame([{"ledger_type": key, "rows": value} for key, value in ledger_counts.items()]), use_container_width=True)
    if rows:
        visible = pd.DataFrame(rows)
        st.dataframe(visible, use_container_width=True)
        st.download_button("Download all local rows", visible.to_csv(index=False).encode("utf-8"), file_name="local_control_rows.csv", mime="text/csv")
    audit = store.load_audit_log(limit=250)
    st.subheader("Audit log")
    if audit:
        st.dataframe(pd.DataFrame(audit), use_container_width=True)
    else:
        st.info("No local audit events found yet.")

with tabs[1]:
    st.subheader("Calibration")
    resolved = [row for row in rows if str(row.get("grade") or row.get("result") or "").strip().lower() in {"win", "won", "w", "loss", "lost", "l"}]
    score = brier_score(resolved)
    c1, c2, c3 = st.columns(3)
    c1.metric("Rows", len(rows))
    c2.metric("Resolved win/loss rows", len(resolved))
    c3.metric("Brier score", "N/A" if score is None else f"{score:.4f}")
    buckets = calibration_buckets(resolved)
    if buckets:
        bucket_df = pd.DataFrame(buckets)
        st.dataframe(bucket_df, use_container_width=True)
        st.bar_chart(bucket_df.set_index("bucket")[["expected_win_rate", "actual_win_rate"]])
    else:
        st.info("No graded rows with usable probabilities were found.")
    st.dataframe(pd.DataFrame(odds_band_summary(resolved)), use_container_width=True)

with tabs[2]:
    st.subheader("Bankroll risk")
    bankroll = st.number_input("Bankroll units", min_value=1.0, value=100.0, step=10.0)
    mode = st.selectbox("Stake mode", ["flat", "conservative_kelly"])
    flat_units = st.number_input("Flat stake units", min_value=0.1, value=1.0, step=0.1)
    max_daily = st.number_input("Max daily exposure %", min_value=0.1, max_value=100.0, value=5.0, step=0.5) / 100.0
    max_sport = st.number_input("Max sport exposure %", min_value=0.1, max_value=100.0, value=5.0, step=0.5) / 100.0
    max_event = st.number_input("Max event exposure %", min_value=0.1, max_value=100.0, value=2.0, step=0.5) / 100.0
    warnings = correlation_warnings(rows)
    for warning in warnings:
        st.warning(warning)
    review_rows = []
    for row in rows:
        suggestion = suggest_stake(row, bankroll=float(bankroll), mode=mode, flat_units=float(flat_units), max_daily_exposure_pct=float(max_daily), max_sport_exposure_pct=float(max_sport), max_event_exposure_pct=float(max_event))
        output = dict(row)
        output["suggested_stake_units"] = suggestion.stake
        output["stake_blocked"] = suggestion.blocked
        output["stake_reason"] = suggestion.reason
        review_rows.append(output)
    if review_rows:
        st.dataframe(pd.DataFrame(review_rows), use_container_width=True)
    else:
        st.info("No rows available for bankroll review.")
    st.caption("Cooldown and drawdown automation remain safe placeholders.")

with tabs[3]:
    st.subheader("Manual license tracking")
    with st.form("local_control_license_form"):
        client_name = st.text_input("Client name")
        client_status = st.selectbox("Client status", ["trial", "active", "inactive", "expired"])
        subscription_tier = st.text_input("Subscription tier", "private_beta")
        manual_payment_status = st.text_input("Manual payment status", "manual")
        renewal_date = st.text_input("Renewal date", "")
        notes = st.text_area("Notes", "")
        future_stripe_ready = st.checkbox("Future Stripe-ready placeholder", value=False)
        submitted = st.form_submit_button("Save local license record")
    if submitted:
        if not client_name.strip():
            st.error("Client name is required.")
        else:
            upsert_license_record(make_license_record(client_name, client_status, subscription_tier, manual_payment_status, renewal_date, notes, future_stripe_ready))
            st.success("Manual local license record saved.")
    records = load_license_records()
    if records:
        df = pd.DataFrame([asdict(record) for record in records])
        st.dataframe(df, use_container_width=True)
        st.download_button("Download local license CSV", df.to_csv(index=False).encode("utf-8"), file_name="local_license_status.csv", mime="text/csv")
    else:
        st.info("No local license records found yet.")
    st.caption("Manual license tracking only. No payment processing.")

with tabs[4]:
    st.subheader("Learning safety")
    safe_rows, blocked_rows = split_learning_safe_rows(rows)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total local rows", len(rows))
    c2.metric("Learning-safe rows", len(safe_rows))
    c3.metric("Blocked/review rows", len(blocked_rows))
    if safe_rows:
        df = pd.DataFrame(safe_rows)
        st.dataframe(df, use_container_width=True)
        st.download_button("Download learning-safe CSV", df.to_csv(index=False).encode("utf-8"), file_name="learning_safe_rows.csv", mime="text/csv")
    upload = st.file_uploader("Preview learning-safe CSV", type=["csv"])
    if upload is not None:
        try:
            st.dataframe(pd.read_csv(upload).head(100), use_container_width=True)
            st.caption("Preview only. This does not train or overwrite memory.")
        except Exception as exc:
            st.warning(f"Could not preview CSV: {exc}")
    version_label = st.text_input("Version label placeholder", "manual")
    st.code(str(version_placeholder_path(version_label)))
    confirmation = st.text_input("Reset confirmation placeholder", "")
    if reset_confirmation_matches(confirmation):
        st.error("Reset confirmation entered. This page still does not delete memory automatically.")
    if blocked_rows:
        with st.expander("Blocked/review rows"):
            st.dataframe(pd.DataFrame(blocked_rows), use_container_width=True)

with tabs[5]:
    st.subheader("Workflow guide")
    st.markdown(
        """
1. Run Pro Predictor Volume or upload rows.
2. Use Odds Lock Pro to create research or official locks.
3. Verify saved rows in Local First Admin / Storage tab.
4. Check individual proof IDs in Proof Center.
5. Export reports in Report Studio.
6. Review bankroll risk and correlation before client use.
7. Review calibration after grading.
8. Export learning-safe rows only after grading and price/probability checks.
"""
    )

with tabs[6]:
    st.subheader("Local alerts/status")
    st.write({
        "storage_mode": "sqlite" if store.using_sqlite else "csv_fallback",
        "sqlite_error": store.sqlite_error,
        "local_rows": len(rows),
        "audit_events": len(store.load_audit_log(limit=250)),
        "correlation_warnings": len(correlation_warnings(rows)),
    })
