from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.market_workflow_integration import (
    build_market_workflow_integration_from_text,
    export_flow_steps_csv,
    export_handoff_manifest_json,
    export_step_status_csv,
    export_workflow_checks_csv,
    export_workflow_integration_json,
    export_workflow_manifest_json,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Market Workflow Integration", layout="wide")
LANG = render_app_sidebar("market_workflow_integration", language_key="market_workflow_integration_language")
REPORT_KEY = "market_workflow_integration_report"
DEFAULT_PAGE_TEXT = "pages/market_optimizer.py pages/market_dashboard_bridge.py pages/market_workflow_integration.py pages/real_page_wiring_audit.py"

TEXT = {
    "en": {
        "title": "Workflow Check",
        "caption": "Checks whether the Market Optimizer → Dashboard Bridge → proof/review workflow is wired correctly.",
        "help": "This is a diagnostic page. Normally you do not paste anything here. Run Market Optimizer and Dashboard Bridge first, then press Verify workflow.",
        "workspace_id": "Workspace ID", "source": "Source check", "run": "Verify workflow", "advanced": "Advanced manual input",
        "optimizer_json": "Manual Market Optimizer JSON", "bridge_json": "Manual Dashboard Bridge JSON", "sidebar_text": "Manual page-navigation text", "page_inventory_csv": "Optional page inventory CSV",
        "summary": "Summary", "steps": "Flow steps", "step_status": "Step status", "checks": "Checks", "actions": "Next actions", "handoff": "Handoff", "safety": "Safety details",
        "no_report": "Verify the workflow to view outputs.", "missing": "Run Market Optimizer and Dashboard Bridge first, or paste their JSON exports in Advanced.",
    },
    "es": {
        "title": "Revisión de Workflow",
        "caption": "Verifica que Market Optimizer → Dashboard Bridge → proof/review esté conectado correctamente.",
        "help": "Esta es una página de diagnóstico. Normalmente no pegas nada aquí. Ejecuta Market Optimizer y Dashboard Bridge primero, luego presiona Verificar workflow.",
        "workspace_id": "ID de workspace", "source": "Revisión de fuente", "run": "Verificar workflow", "advanced": "Entrada manual avanzada",
        "optimizer_json": "JSON manual Market Optimizer", "bridge_json": "JSON manual Dashboard Bridge", "sidebar_text": "Texto manual de navegación", "page_inventory_csv": "CSV inventario de páginas opcional",
        "summary": "Resumen", "steps": "Flow steps", "step_status": "Estado steps", "checks": "Checks", "actions": "Siguientes acciones", "handoff": "Handoff", "safety": "Detalles de seguridad",
        "no_report": "Verifica el workflow para ver outputs.", "missing": "Ejecuta Market Optimizer y Dashboard Bridge primero, o pega sus JSON exports en Avanzado.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "workflow"


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
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="market_workflow_workspace_id"))
auto_optimizer_json, optimizer_found = _session_json("market_optimizer_preview_report")
auto_bridge_json, bridge_found = _session_json("market_dashboard_bridge_report")

st.subheader(t("source"))
cols = st.columns(3)
cols[0].metric("Market Optimizer", "found" if optimizer_found else "missing")
cols[1].metric("Dashboard Bridge", "found" if bridge_found else "missing")
cols[2].metric("workspace", workspace_id)
if not (optimizer_found and bridge_found):
    st.warning(t("missing"))

with st.expander(t("advanced"), expanded=False):
    optimizer_json = st.text_area(t("optimizer_json"), value=auto_optimizer_json, key="market_workflow_optimizer_json", height=160)
    bridge_json = st.text_area(t("bridge_json"), value=auto_bridge_json, key="market_workflow_bridge_json", height=160)
    sidebar_text = st.text_area(t("sidebar_text"), value=DEFAULT_PAGE_TEXT, key="market_workflow_sidebar_text", height=90)
    page_inventory_csv = st.text_area(t("page_inventory_csv"), value="", key="market_workflow_page_inventory_csv", height=100)

if st.button(t("run"), key="market_workflow_run", type="primary"):
    st.session_state[REPORT_KEY] = build_market_workflow_integration_from_text(workspace_id, optimizer_json or auto_optimizer_json, bridge_json or auto_bridge_json, sidebar_text, page_inventory_csv)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

metrics = st.columns(7)
metrics[0].metric("status", report.get("workflow_status", ""))
metrics[1].metric("tracking", report.get("tracking_row_count", 0))
metrics[2].metric("handoff", report.get("handoff_row_count", 0))
metrics[3].metric("steps", len(report.get("flow_steps") or []))
metrics[4].metric("pass", report.get("pass_count", 0))
metrics[5].metric("warn", report.get("warn_count", 0))
metrics[6].metric("fail", report.get("fail_count", 0))

tabs = st.tabs([t("summary"), t("steps"), t("step_status"), t("checks"), t("actions"), t("handoff")])
with tabs[0]:
    st.json({"workspace_id": report.get("workspace_id"), "workflow_status": report.get("workflow_status"), "tracking_row_count": report.get("tracking_row_count"), "handoff_row_count": report.get("handoff_row_count"), "preview_only": report.get("preview_only"), "live_changes": report.get("live_changes")})
with tabs[1]:
    st.dataframe(pd.DataFrame(report.get("flow_steps") or []), use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(pd.DataFrame(report.get("step_status_rows") or []), use_container_width=True, hide_index=True)
with tabs[3]:
    st.dataframe(pd.DataFrame(report.get("workflow_checks") or []), use_container_width=True, hide_index=True)
with tabs[4]:
    st.write(report.get("next_actions") or [])
with tabs[5]:
    st.json(report.get("handoff_manifest") or {})

with st.expander(t("safety"), expanded=False):
    st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('workflow_hash'))}"
st.download_button("Download workflow JSON", export_workflow_integration_json(report).encode("utf-8"), file_name=f"aba_market_workflow_{suffix}.json", mime="application/json", key=f"market_workflow_json_{safe_text(report.get('workflow_hash'))}")
st.download_button("Download steps CSV", export_flow_steps_csv(report).encode("utf-8"), file_name=f"aba_market_workflow_steps_{suffix}.csv", mime="text/csv", key=f"market_workflow_steps_{safe_text(report.get('workflow_hash'))}")
st.download_button("Download status CSV", export_step_status_csv(report).encode("utf-8"), file_name=f"aba_market_workflow_status_{suffix}.csv", mime="text/csv", key=f"market_workflow_status_{safe_text(report.get('workflow_hash'))}")
st.download_button("Download checks CSV", export_workflow_checks_csv(report).encode("utf-8"), file_name=f"aba_market_workflow_checks_{suffix}.csv", mime="text/csv", key=f"market_workflow_checks_{safe_text(report.get('workflow_hash'))}")
st.download_button("Download handoff JSON", export_handoff_manifest_json(report).encode("utf-8"), file_name=f"aba_market_workflow_handoff_{suffix}.json", mime="application/json", key=f"market_workflow_handoff_{safe_text(report.get('workflow_hash'))}")
st.download_button("Download manifest JSON", export_workflow_manifest_json(report).encode("utf-8"), file_name=f"aba_market_workflow_manifest_{suffix}.json", mime="application/json", key=f"market_workflow_manifest_{safe_text(report.get('workflow_hash'))}")
