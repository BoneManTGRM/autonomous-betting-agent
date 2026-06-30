from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.market_dashboard_bridge import (
    build_market_dashboard_bridge_from_text,
    export_dashboard_cards_json,
    export_market_bridge_checks_csv,
    export_market_bridge_json,
    export_market_bridge_manifest_json,
    export_proof_handoff_csv,
    export_segment_summary_csv,
    export_tracking_schema_csv,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Market Dashboard Bridge", layout="wide")
LANG = render_app_sidebar("market_dashboard_bridge", language_key="market_dashboard_bridge_language")
REPORT_KEY = "market_dashboard_bridge_report"

TEXT = {
    "en": {
        "title": "Dashboard Bridge",
        "caption": "Turns the latest Market Optimizer result into dashboard cards and proof-handoff rows.",
        "help": "Use this only after Market Optimizer. The page automatically uses the latest optimizer result when available. Manual JSON and CSV boxes are under Advanced.",
        "workspace_id": "Workspace ID", "source": "Source check", "run": "Build dashboard bridge", "advanced": "Advanced manual input",
        "optimizer_json": "Manual optimizer JSON", "market_csv": "Optional market rows CSV", "chain_csv": "Optional chain rows CSV", "avoid_csv": "Optional avoid rows CSV",
        "summary": "Summary", "cards": "Dashboard cards", "tracking": "Tracking rows", "segments": "Segments", "handoff": "Proof handoff", "checks": "Checks", "safety": "Safety details",
        "no_report": "Build the dashboard bridge to view outputs.", "no_source": "No Market Optimizer result found. Run Market Optimizer first or paste JSON in Advanced.",
    },
    "es": {
        "title": "Dashboard Bridge",
        "caption": "Convierte el resultado de Market Optimizer en cards de dashboard y filas proof-handoff.",
        "help": "Usa esto solo después de Market Optimizer. La página usa automáticamente el último resultado disponible. JSON/CSV manuales están en Avanzado.",
        "workspace_id": "ID de workspace", "source": "Revisión de fuente", "run": "Construir dashboard bridge", "advanced": "Entrada manual avanzada",
        "optimizer_json": "JSON optimizer manual", "market_csv": "CSV market opcional", "chain_csv": "CSV chain opcional", "avoid_csv": "CSV avoid opcional",
        "summary": "Resumen", "cards": "Cards dashboard", "tracking": "Filas tracking", "segments": "Segmentos", "handoff": "Proof handoff", "checks": "Checks", "safety": "Detalles de seguridad",
        "no_report": "Construye el dashboard bridge para ver outputs.", "no_source": "No hay resultado de Market Optimizer. Ejecútalo primero o pega JSON en Avanzado.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "bridge"


def _session_json(key: str) -> tuple[str, int]:
    value = st.session_state.get(key) or {}
    if not value:
        return "", 0
    try:
        return json.dumps(value), 1
    except Exception:
        return "", 0


st.title(t("title"))
st.caption(t("caption"))
st.info(t("help"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="market_bridge_workspace_id"))
auto_optimizer_json, optimizer_found = _session_json("market_optimizer_preview_report")

st.subheader(t("source"))
cols = st.columns(2)
cols[0].metric("Market Optimizer result", "found" if optimizer_found else "missing")
cols[1].metric("workspace", workspace_id)
if not optimizer_found:
    st.warning(t("no_source"))

with st.expander(t("advanced"), expanded=False):
    optimizer_json = st.text_area(t("optimizer_json"), value=auto_optimizer_json, key="market_bridge_optimizer_json", height=180)
    market_csv = st.text_area(t("market_csv"), value="", key="market_bridge_market_csv", height=120)
    chain_csv = st.text_area(t("chain_csv"), value="", key="market_bridge_chain_csv", height=120)
    avoid_csv = st.text_area(t("avoid_csv"), value="", key="market_bridge_avoid_csv", height=120)

if st.button(t("run"), key="market_bridge_run", type="primary"):
    st.session_state[REPORT_KEY] = build_market_dashboard_bridge_from_text(workspace_id, optimizer_json or auto_optimizer_json, market_csv, chain_csv, avoid_csv)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

metrics = st.columns(7)
metrics[0].metric("status", report.get("bridge_status", ""))
metrics[1].metric("markets", report.get("market_row_count", 0))
metrics[2].metric("tracking", report.get("tracking_row_count", 0))
metrics[3].metric("chains", report.get("chain_row_count", 0))
metrics[4].metric("avoid", report.get("avoid_row_count", 0))
metrics[5].metric("warn", report.get("warn_count", 0))
metrics[6].metric("fail", report.get("fail_count", 0))

tabs = st.tabs([t("summary"), t("cards"), t("tracking"), t("segments"), t("handoff"), t("checks")])
with tabs[0]:
    st.json({"workspace_id": report.get("workspace_id"), "bridge_status": report.get("bridge_status"), "market_row_count": report.get("market_row_count"), "tracking_row_count": report.get("tracking_row_count"), "preview_only": report.get("preview_only"), "live_changes": report.get("live_changes")})
with tabs[1]:
    st.json(report.get("dashboard_cards") or {})
with tabs[2]:
    st.dataframe(pd.DataFrame(report.get("tracking_rows") or []), use_container_width=True, hide_index=True)
with tabs[3]:
    st.dataframe(pd.DataFrame(report.get("segment_summary_rows") or []), use_container_width=True, hide_index=True)
with tabs[4]:
    st.dataframe(pd.DataFrame(report.get("proof_handoff_rows") or []), use_container_width=True, hide_index=True)
with tabs[5]:
    st.dataframe(pd.DataFrame(report.get("bridge_checks") or []), use_container_width=True, hide_index=True)

with st.expander(t("safety"), expanded=False):
    st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('bridge_hash'))}"
st.download_button("Download bridge JSON", export_market_bridge_json(report).encode("utf-8"), file_name=f"aba_market_bridge_{suffix}.json", mime="application/json", key=f"market_bridge_json_{safe_text(report.get('bridge_hash'))}")
st.download_button("Download dashboard cards JSON", export_dashboard_cards_json(report).encode("utf-8"), file_name=f"aba_market_dashboard_cards_{suffix}.json", mime="application/json", key=f"market_bridge_cards_{safe_text(report.get('bridge_hash'))}")
st.download_button("Download tracking CSV", export_tracking_schema_csv(report).encode("utf-8"), file_name=f"aba_market_tracking_{suffix}.csv", mime="text/csv", key=f"market_bridge_tracking_{safe_text(report.get('bridge_hash'))}")
st.download_button("Download segments CSV", export_segment_summary_csv(report).encode("utf-8"), file_name=f"aba_market_segments_{suffix}.csv", mime="text/csv", key=f"market_bridge_segments_{safe_text(report.get('bridge_hash'))}")
st.download_button("Download proof handoff CSV", export_proof_handoff_csv(report).encode("utf-8"), file_name=f"aba_market_proof_handoff_{suffix}.csv", mime="text/csv", key=f"market_bridge_handoff_{safe_text(report.get('bridge_hash'))}")
st.download_button("Download checks CSV", export_market_bridge_checks_csv(report).encode("utf-8"), file_name=f"aba_market_bridge_checks_{suffix}.csv", mime="text/csv", key=f"market_bridge_checks_{safe_text(report.get('bridge_hash'))}")
st.download_button("Download manifest JSON", export_market_bridge_manifest_json(report).encode("utf-8"), file_name=f"aba_market_bridge_manifest_{suffix}.json", mime="application/json", key=f"market_bridge_manifest_{safe_text(report.get('bridge_hash'))}")
