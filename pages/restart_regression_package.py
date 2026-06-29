from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.restart_regression_package import (
    build_restart_regression_package_from_text,
    export_restart_checks_csv,
    export_restart_manifest_json,
    export_restart_regression_json,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Restart Regression Package", layout="wide")
LANG = render_app_sidebar("restart_regression_package", language_key="restart_regression_language")

REPORT_KEY = "restart_regression_package_report"

TEXT = {
    "en": {
        "title": "Restart Regression Package",
        "caption": "Verify that dashboard and checklist packages survive export, reload, and rebuild without changing core metrics.",
        "workspace_id": "Workspace ID",
        "proof_csv": "Proof / source rows CSV",
        "history_csv": "Historical graded rows CSV",
        "decision_csv": "Decision preview CSV",
        "dashboard_json": "Optional dashboard package JSON",
        "checklist_json": "Optional checklist package JSON",
        "run": "Run restart regression",
        "summary": "Restart summary",
        "checks": "Regression checks",
        "dashboard": "Rebuilt dashboard manifest",
        "checklist": "Rebuilt checklist summary",
        "safety": "Safety gates",
        "download_json": "Download restart JSON",
        "download_checks": "Download checks CSV",
        "download_manifest": "Download manifest JSON",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Run restart regression to view outputs.",
    },
    "es": {
        "title": "Restart Regression Package",
        "caption": "Verifica que dashboard y checklist sobreviven export, reload y rebuild sin cambiar métricas core.",
        "workspace_id": "ID de workspace",
        "proof_csv": "CSV proof / filas fuente",
        "history_csv": "CSV histórico calificado",
        "decision_csv": "CSV decision preview",
        "dashboard_json": "JSON dashboard package opcional",
        "checklist_json": "JSON checklist package opcional",
        "run": "Ejecutar restart regression",
        "summary": "Resumen restart",
        "checks": "Regression checks",
        "dashboard": "Manifest dashboard reconstruido",
        "checklist": "Resumen checklist reconstruido",
        "safety": "Safety gates",
        "download_json": "Descargar JSON restart",
        "download_checks": "Descargar CSV checks",
        "download_manifest": "Descargar JSON manifest",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Ejecuta restart regression para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "restart"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="restart_regression_workspace_id"))

proof_csv = st.text_area(t("proof_csv"), value="", key="restart_regression_proof_csv", height=180)
history_csv = st.text_area(t("history_csv"), value="", key="restart_regression_history_csv", height=160)
decision_csv = st.text_area(t("decision_csv"), value="", key="restart_regression_decision_csv", height=160)
dashboard_json = st.text_area(t("dashboard_json"), value="", key="restart_regression_dashboard_json", height=140)
checklist_json = st.text_area(t("checklist_json"), value="", key="restart_regression_checklist_json", height=140)

if st.button(t("run"), key="restart_regression_run"):
    st.session_state[REPORT_KEY] = build_restart_regression_package_from_text(workspace_id, proof_csv, history_csv, decision_csv, dashboard_json, checklist_json)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("status", report.get("restart_status", ""))
metrics[1].metric("proof", report.get("proof_row_count", 0))
metrics[2].metric("decision", report.get("decision_row_count", 0))
metrics[3].metric("pass", report.get("pass_count", 0))
metrics[4].metric("warn", report.get("warn_count", 0))
metrics[5].metric("fail", report.get("fail_count", 0))
metrics[6].metric("history", report.get("history_row_count", 0))
metrics[7].metric("hash", _fragment(report.get("restart_regression_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "restart_regression_id": report.get("restart_regression_id"),
    "restart_regression_hash": report.get("restart_regression_hash"),
    "mode": report.get("mode"),
    "restart_status": report.get("restart_status"),
    "proof_row_count": report.get("proof_row_count"),
    "history_row_count": report.get("history_row_count"),
    "decision_row_count": report.get("decision_row_count"),
    "pass_count": report.get("pass_count"),
    "warn_count": report.get("warn_count"),
    "fail_count": report.get("fail_count"),
    "dashboard_original_fingerprint": report.get("dashboard_original_fingerprint"),
    "dashboard_rebuilt_fingerprint": report.get("dashboard_rebuilt_fingerprint"),
    "checklist_original_fingerprint": report.get("checklist_original_fingerprint"),
    "checklist_rebuilt_fingerprint": report.get("checklist_rebuilt_fingerprint"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('checks')}")
st.dataframe(pd.DataFrame(report.get("check_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('dashboard')}")
st.json(report.get("rebuilt_dashboard_manifest") or {})

st.markdown(f"### {t('checklist')}")
st.json(report.get("rebuilt_checklist_summary") or {})

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('restart_regression_hash'))}"
st.download_button(t("download_json"), export_restart_regression_json(report).encode("utf-8"), file_name=f"aba_restart_regression_{suffix}.json", mime="application/json", key=f"restart_regression_json_{safe_text(report.get('restart_regression_hash'))}")
st.download_button(t("download_checks"), export_restart_checks_csv(report).encode("utf-8"), file_name=f"aba_restart_regression_checks_{suffix}.csv", mime="text/csv", key=f"restart_regression_checks_{safe_text(report.get('restart_regression_hash'))}")
st.download_button(t("download_manifest"), export_restart_manifest_json(report).encode("utf-8"), file_name=f"aba_restart_regression_manifest_{suffix}.json", mime="application/json", key=f"restart_regression_manifest_{safe_text(report.get('restart_regression_hash'))}")
