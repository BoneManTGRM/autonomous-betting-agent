from __future__ import annotations

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

TEXT = {
    "en": {
        "title": "Subscriber Export Center",
        "caption": "Admin dashboard and client-safe export center for subscriber reports and ledgers.",
        "workspace_id": "Workspace ID",
        "intelligence_json": "Subscriber Intelligence JSON",
        "ledger_json": "Subscriber Ledger JSON",
        "profiles_csv": "Optional Profiles CSV override",
        "run": "Build export center",
        "summary": "Export summary",
        "admin": "Admin dashboard",
        "packages": "Export packages",
        "index": "Package index",
        "partners": "Partner summary",
        "plans": "Plan distribution",
        "risks": "Risk distribution",
        "checks": "Checks",
        "safety": "Safety gates",
        "download_json": "Download export center JSON",
        "download_admin": "Download admin dashboard JSON",
        "download_index": "Download package index CSV",
        "download_client": "Download client-safe rows CSV",
        "download_partner": "Download partner summary CSV",
        "download_plan": "Download plan distribution CSV",
        "download_risk": "Download risk distribution CSV",
        "download_checks": "Download checks CSV",
        "download_manifest": "Download manifest JSON",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Build the export center to view outputs.",
    },
    "es": {
        "title": "Subscriber Export Center",
        "caption": "Dashboard admin y export center client-safe para reportes y ledgers de subscribers.",
        "workspace_id": "ID de workspace",
        "intelligence_json": "JSON Subscriber Intelligence",
        "ledger_json": "JSON Subscriber Ledger",
        "profiles_csv": "CSV perfiles opcional",
        "run": "Construir export center",
        "summary": "Resumen export",
        "admin": "Dashboard admin",
        "packages": "Export packages",
        "index": "Package index",
        "partners": "Partner summary",
        "plans": "Plan distribution",
        "risks": "Risk distribution",
        "checks": "Checks",
        "safety": "Safety gates",
        "download_json": "Descargar JSON export center",
        "download_admin": "Descargar JSON dashboard admin",
        "download_index": "Descargar CSV package index",
        "download_client": "Descargar CSV client-safe rows",
        "download_partner": "Descargar CSV partner summary",
        "download_plan": "Descargar CSV plan distribution",
        "download_risk": "Descargar CSV risk distribution",
        "download_checks": "Descargar CSV checks",
        "download_manifest": "Descargar JSON manifest",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Construye el export center para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "export"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="subscriber_export_workspace_id"))
intelligence_json = st.text_area(t("intelligence_json"), value="", key="subscriber_export_intelligence_json", height=200)
ledger_json = st.text_area(t("ledger_json"), value="", key="subscriber_export_ledger_json", height=200)
profiles_csv = st.text_area(t("profiles_csv"), value="", key="subscriber_export_profiles_csv", height=120)

if st.button(t("run"), key="subscriber_export_run"):
    st.session_state[REPORT_KEY] = build_subscriber_export_center_from_text(workspace_id, intelligence_json, ledger_json, profiles_csv)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
admin = report.get("admin_dashboard_summary") or {}
metrics = st.columns(8)
metrics[0].metric("status", report.get("export_status", ""))
metrics[1].metric("packages", report.get("package_count", 0))
metrics[2].metric("ready", admin.get("ready_package_count", 0))
metrics[3].metric("review", admin.get("review_required_count", 0))
metrics[4].metric("bets", admin.get("total_bet_count", 0))
metrics[5].metric("ROI", admin.get("portfolio_roi"))
metrics[6].metric("fail", report.get("fail_count", 0))
metrics[7].metric("hash", _fragment(report.get("export_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "export_run_id": report.get("export_run_id"),
    "export_hash": report.get("export_hash"),
    "mode": report.get("mode"),
    "export_status": report.get("export_status"),
    "package_count": report.get("package_count"),
    "pass_count": report.get("pass_count"),
    "warn_count": report.get("warn_count"),
    "fail_count": report.get("fail_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('admin')}")
st.json(report.get("admin_dashboard_summary") or {})

st.markdown(f"### {t('packages')}")
st.json(report.get("export_packages") or [])

st.markdown(f"### {t('index')}")
st.dataframe(pd.DataFrame(report.get("package_index_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('partners')}")
st.dataframe(pd.DataFrame(report.get("partner_summary_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('plans')}")
st.dataframe(pd.DataFrame(report.get("plan_distribution_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('risks')}")
st.dataframe(pd.DataFrame(report.get("risk_distribution_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('checks')}")
st.dataframe(pd.DataFrame(report.get("export_checks") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

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
