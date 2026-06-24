from __future__ import annotations

import streamlit as st

from autonomous_betting_agent.explanations import build_client_safe_pick_summary
from autonomous_betting_agent.report_exports import render_html_report, render_markdown_report, render_messenger_report
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Buyer Demo Local", layout="wide")
render_app_sidebar("buyer_demo_local", language_key="buyer_demo_local_language")

st.title("Buyer Demo Local")
st.caption("Sample local-first buyer walkthrough. No API keys or cloud server required.")

st.warning("Demo only. ABA Signal Pro is for analytics, proof tracking, reporting, and risk review. It does not guarantee outcomes or returns.")

sample_rows = [
    {
        "proof_id": "DEMO-001",
        "locked_at_utc": "2026-06-23T10:00:00+00:00",
        "event_start_time": "2026-06-23T12:00:00+00:00",
        "event_name": "Demo Team A vs Demo Team B",
        "prediction": "Demo Team A",
        "market": "moneyline",
        "sport": "soccer",
        "decimal_price": 1.82,
        "odds_audit_status": "pass",
        "pattern_points": 82,
        "model_probability": 0.61,
        "model_market_edge": 0.04,
        "bookmaker_count": 5,
        "grade": "pending",
        "ledger_type": "official",
    },
    {
        "proof_id": "DEMO-002",
        "locked_at_utc": "2026-06-23T10:30:00+00:00",
        "event_start_time": "2026-06-23T13:00:00+00:00",
        "event_name": "Demo Club C vs Demo Club D",
        "prediction": "Over 2.5",
        "market": "total",
        "sport": "soccer",
        "decimal_price": 1.95,
        "odds_audit_status": "pass",
        "pattern_points": 76,
        "model_probability": 0.57,
        "model_market_edge": 0.02,
        "bookmaker_count": 4,
        "grade": "pending",
        "ledger_type": "research",
    },
]

st.header("What this shows")
st.markdown(
    """
- Local-first proof tracking without a cloud server.
- Timestamped proof rows with proof IDs.
- Client-safe pick explanations.
- Local Report Studio output.
- Clear separation between official and research rows.
- Disclaimers that avoid guaranteed outcome language.
"""
)

st.header("Sample proof explanations")
for row in sample_rows:
    st.info(build_client_safe_pick_summary(row))

st.header("Sample report outputs")
markdown_report = render_markdown_report(sample_rows, title="ABA Signal Pro Buyer Demo", client_name="Demo Buyer", public_safe=False)
html_report = render_html_report(sample_rows, title="ABA Signal Pro Buyer Demo", client_name="Demo Buyer", public_safe=False)
message_report = render_messenger_report(sample_rows, title="ABA Signal Pro Buyer Demo")

st.text_area("Messenger-ready summary", message_report, height=120)
st.download_button("Download demo Markdown", markdown_report.encode("utf-8"), file_name="aba_buyer_demo.md", mime="text/markdown")
st.download_button("Download demo HTML / print-to-PDF", html_report.encode("utf-8"), file_name="aba_buyer_demo.html", mime="text/html")

with st.expander("Markdown preview"):
    st.text(markdown_report)

st.header("Local-first buyer summary")
st.markdown(
    """
ABA Signal Pro can be shown as a local-first analytics and reporting workflow:

1. Scan or upload rows.
2. Review odds, market support, and proof readiness.
3. Lock rows before event start.
4. Save rows locally to SQLite/CSV fallback.
5. Verify proof IDs.
6. Export client-ready reports.
7. Review calibration and learning safety after grading.
"""
)
