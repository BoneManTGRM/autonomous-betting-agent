from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.subscriber_export_center import (
    build_subscriber_export_center_from_text,
    export_admin_dashboard_json,
    export_client_safe_rows_csv,
    export_export_checks_csv,
    export_export_manifest_json,
    export_package_index_csv,
    export_partner_summary_csv,
    export_plan_distribution_csv,
    export_risk_distribution_csv,
    export_subscriber_export_center_json,
)

st.set_page_config(page_title="Subscriber Export Center", layout="wide")
LANG = render_app_sidebar("subscriber_export_center", language_key="subscriber_export_center_language")
REPORT_KEY = "subscriber_export_center_report"
PAGE_CONTRACT_FIELDS = ("schema_version", "workspace_id", "export_run_id", "export_hash", "mode", "export_status", "package_count", "admin_dashboard_summary", "export_packages", "package_index_rows", "partner_summary_rows", "plan_distribution_rows", "risk_distribution_rows", "export_checks", "safety_gates", "preview_only", "files_written", "live_changes")

TEXT = {
    "en": {
        "title": "Subscriber Export Center", "caption": "Packages subscriber reports after Subscriber Intelligence and Subscriber Ledger are built.", "help": "Run Subscriber Intelligence and Subscriber Ledger first. Manual JSON boxes are under Advanced.",
        "workspace_id": "Workspace ID", "source": "Source check", "run": "Build export package", "advanced": "Advanced manual input", "intelligence_json": "Manual Subscriber Intelligence JSON", "ledger_json": "Manual Subscriber Ledger JSON", "profiles_csv": "Optional manual profiles CSV",
        "summary": "Export summary", "admin": "Admin dashboard", "packages": "Export packages", "index": "Package index", "partners": "Partner summary", "plans": "Plan distribution", "risks": "Risk distribution", "checks": "Checks", "safety": "Safety details", "download_json": "Download export JSON", "download_admin": "Download admin JSON", "download_index": "Download index CSV", "download_client": "Download client CSV", "download_partner": "Download partner CSV", "download_plan": "Download plan CSV", "download_risk": "Download risk CSV", "download_checks": "Download checks CSV", "download_manifest": "Download manifest JSON", "preview_only": "Preview only", "no_files": "No files written.", "no_live": "No live changes.", "no_report": "Build the export package to view outputs.", "missing": "Run the missing subscriber pages first, or paste their JSON exports under Advanced.",
    },
    "es": {
        "title": "Export Center de Subscribers", "caption": "Empaqueta reportes de subscriber después de Subscriber Intelligence y Subscriber Ledger.", "help": "Ejecuta Subscriber Intelligence y Subscriber Ledger primero. Los JSON manuales están en Avanzado.",
        "workspace_id": "ID de workspace", "source": "Revisión de fuente", "run": "Construir paquete export", "advanced": "Entrada manual avanzada", "intelligence_json": "JSON manual Subscriber Intelligence", "ledger_json": "JSON manual Subscriber Ledger", "profiles_csv": "CSV perfiles manual opcional",
        "summary": "Resumen export", "admin": "Dashboard admin", "packages": "Paquetes export", "index": "Índice paquetes", "partners": "Resumen partner", "plans": "Distribución planes", "risks": "Distribución riesgos", "checks": "Checks", "safety": "Detalles de seguridad", "download_json": "Descargar JSON export", "download_admin": "Descargar JSON admin", "download_index": "Descargar CSV índice", "download_client": "Descargar CSV cliente", "download_partner": "Descargar CSV partner", "download_plan": "Descargar CSV plan", "download_risk": "Descargar CSV riesgo", "download_checks": "Descargar CSV checks", "download_manifest": "Descargar JSON manifest", "preview_only": "Solo preview", "no_files": "No escribe archivos.", "no_live": "No hace cambios live.", "no_report": "Construye el paquete export para ver outputs.", "missing": "Ejecuta las páginas subscriber faltantes primero, o pega sus JSON exports en Avanzado.",
    },
}

def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)

def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "export"

def _session_json(key: str) -> tuple[str, int]:
    value = st.session_state.get(key) or {}
    if not value:
        return "", 0
    try:
        return json.dumps(value), 1
    except Exception:
        return "", 0

st.title(t("title")); st.caption(t("caption")); st.info(t("help"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="subscriber_export_workspace_id"))
auto_intelligence_json, intelligence_found = _session_json("subscriber_intelligence_report")
auto_ledger_json, ledger_found = _session_json("subscriber_ledger_report")
st.subheader(t("source")); cols = st.columns(3); cols[0].metric("Subscriber Intelligence", "found" if intelligence_found else "missing"); cols[1].metric("Subscriber Ledger", "found" if ledger_found else "missing"); cols[2].metric("workspace", workspace_id)
if not (intelligence_found and ledger_found): st.warning(t("missing"))
with st.expander(t("advanced"), expanded=False):
    intelligence_json = st.text_area(t("intelligence_json"), value=auto_intelligence_json, key="subscriber_export_intelligence_json", height=160)
    ledger_json = st.text_area(t("ledger_json"), value=auto_ledger_json, key="subscriber_export_ledger_json", height=160)
    profiles_csv = st.text_area(t("profiles_csv"), value="", key="subscriber_export_profiles_csv", height=120)
if st.button(t("run"), key="subscriber_export_run", type="primary"):
    st.session_state[REPORT_KEY] = build_subscriber_export_center_from_text(workspace_id, intelligence_json or auto_intelligence_json, ledger_json or auto_ledger_json, profiles_csv)
report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report")); st.stop()
admin = report.get("admin_dashboard_summary") or {}
metrics = st.columns(7); metrics[0].metric("status", report.get("export_status", "")); metrics[1].metric("packages", report.get("package_count", 0)); metrics[2].metric("ready", admin.get("ready_package_count", 0)); metrics[3].metric("review", admin.get("review_required_count", 0)); metrics[4].metric("items", admin.get("total_bet_count", 0)); metrics[5].metric("ROI", admin.get("portfolio_roi")); metrics[6].metric("fail", report.get("fail_count", 0))
tabs = st.tabs([t("summary"), t("admin"), t("packages"), t("index"), t("partners"), t("plans"), t("risks"), t("checks")])
with tabs[0]: st.json({field: report.get(field) for field in PAGE_CONTRACT_FIELDS})
with tabs[1]: st.json(admin)
with tabs[2]: st.json(report.get("export_packages") or [])
with tabs[3]: st.dataframe(pd.DataFrame(report.get("package_index_rows") or []), use_container_width=True, hide_index=True)
with tabs[4]: st.dataframe(pd.DataFrame(report.get("partner_summary_rows") or []), use_container_width=True, hide_index=True)
with tabs[5]: st.dataframe(pd.DataFrame(report.get("plan_distribution_rows") or []), use_container_width=True, hide_index=True)
with tabs[6]: st.dataframe(pd.DataFrame(report.get("risk_distribution_rows") or []), use_container_width=True, hide_index=True)
with tabs[7]: st.dataframe(pd.DataFrame(report.get("export_checks") or []), use_container_width=True, hide_index=True)
with st.expander(t("safety"), expanded=False): st.json(report.get("safety_gates") or {})
suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('export_hash'))}"
st.download_button(t("download_json"), export_subscriber_export_center_json(report).encode("utf-8"), file_name=f"aba_subscriber_export_center_{suffix}.json", mime="application/json", key=f"subscriber_export_json_{safe_text(report.get('export_hash'))}")
st.download_button(t("download_admin"), export_admin_dashboard_json(report).encode("utf-8"), file_name=f"aba_subscriber_admin_dashboard_{suffix}.json", mime="application/json", key=f"subscriber_export_admin_{safe_text(report.get('export_hash'))}")
st.download_button(t("download_index"), export_package_index_csv(report).encode("utf-8"), file_name=f"aba_subscriber_package_index_{suffix}.csv", mime="text/csv", key=f"subscriber_export_index_{safe_text(report.get('export_hash'))}")
st.download_button(t("download_client"), export_client_safe_rows_csv(report).encode("utf-8"), file_name=f"aba_subscriber_client_safe_rows_{suffix}.csv", mime="text/csv", key=f"subscriber_export_client_{safe_text(report.get('export_hash'))}")
st.download_button(t("download_partner"), export_partner_summary_csv(report).encode("utf-8"), file_name=f"aba_subscriber_partner_summary_{suffix}.csv", mime="text/csv", key=f"subscriber_export_partner_{safe_text(report.get('export_hash'))}")
st.download_button(t("download_plan"), export_plan_distribution_csv(report).encode("utf-8"), file_name=f"aba_subscriber_plan_distribution_{suffix}.csv", mime="text/csv", key=f"subscriber_export_plan_{safe_text(report.get('export_hash'))}")
st.download_button(t("download_risk"), export_risk_distribution_csv(report).encode("utf-8"), file_name=f"aba_subscriber_risk_distribution_{suffix}.csv", mime="text/csv", key=f"subscriber_export_risk_{safe_text(report.get('export_hash'))}")
st.download_button(t("download_checks"), export_export_checks_csv(report).encode("utf-8"), file_name=f"aba_subscriber_export_checks_{suffix}.csv", mime="text/csv", key=f"subscriber_export_checks_{safe_text(report.get('export_hash'))}")
st.download_button(t("download_manifest"), export_export_manifest_json(report).encode("utf-8"), file_name=f"aba_subscriber_export_manifest_{suffix}.json", mime="application/json", key=f"subscriber_export_manifest_{safe_text(report.get('export_hash'))}")
