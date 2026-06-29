from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.dashboard_refresh_package import (
    build_dashboard_refresh_package_from_text,
    export_blocker_breakdown_csv,
    export_dashboard_manifest_json,
    export_dashboard_refresh_json,
    export_dashboard_rows_csv,
    export_dashboard_summary_csv,
    export_duplicate_groups_csv,
    export_event_breakdown_csv,
    export_segment_breakdown_csv,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Dashboard Refresh Package", layout="wide")
LANG = render_app_sidebar("dashboard_refresh_package", language_key="dashboard_refresh_language")

REPORT_KEY = "dashboard_refresh_package_report"

TEXT = {
    "en": {
        "title": "Dashboard Refresh Package",
        "caption": "Create dashboard-ready proof metrics from proof rows and accuracy decision preview rows without overwriting live proof data.",
        "workspace_id": "Workspace ID",
        "proof_csv": "Proof / source rows CSV",
        "history_csv": "Historical graded rows CSV",
        "decision_csv": "Optional decision preview CSV",
        "run": "Build dashboard refresh package",
        "summary": "Dashboard summary",
        "rows": "Dashboard rows",
        "actions": "Action breakdown",
        "blockers": "Blocker breakdown",
        "events": "Event breakdown",
        "duplicates": "Duplicate event groups",
        "segments": "Segment breakdown",
        "manifest": "Refresh manifest",
        "safety": "Safety gates",
        "download_json": "Download dashboard JSON",
        "download_summary": "Download summary CSV",
        "download_rows": "Download dashboard rows CSV",
        "download_events": "Download event breakdown CSV",
        "download_duplicates": "Download duplicate groups CSV",
        "download_segments": "Download segment breakdown CSV",
        "download_blockers": "Download blocker breakdown CSV",
        "download_manifest": "Download manifest JSON",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Build the dashboard refresh package to view outputs.",
    },
    "es": {
        "title": "Dashboard Refresh Package",
        "caption": "Crea métricas proof listas para dashboard desde filas proof y decision preview sin sobrescribir proof live.",
        "workspace_id": "ID de workspace",
        "proof_csv": "CSV proof / filas fuente",
        "history_csv": "CSV histórico calificado",
        "decision_csv": "CSV decision preview opcional",
        "run": "Crear dashboard refresh package",
        "summary": "Resumen dashboard",
        "rows": "Filas dashboard",
        "actions": "Desglose de acciones",
        "blockers": "Desglose de bloqueos",
        "events": "Desglose por evento",
        "duplicates": "Grupos duplicados de eventos",
        "segments": "Desglose por segmento",
        "manifest": "Manifest refresh",
        "safety": "Safety gates",
        "download_json": "Descargar JSON dashboard",
        "download_summary": "Descargar CSV resumen",
        "download_rows": "Descargar CSV dashboard rows",
        "download_events": "Descargar CSV eventos",
        "download_duplicates": "Descargar CSV duplicados",
        "download_segments": "Descargar CSV segmentos",
        "download_blockers": "Descargar CSV blockers",
        "download_manifest": "Descargar JSON manifest",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Crea el dashboard refresh package para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "dashboard"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="dashboard_refresh_workspace_id"))

proof_csv = st.text_area(t("proof_csv"), value="", key="dashboard_refresh_proof_csv", height=220)
history_csv = st.text_area(t("history_csv"), value="", key="dashboard_refresh_history_csv", height=180)
decision_csv = st.text_area(t("decision_csv"), value="", key="dashboard_refresh_decision_csv", height=180)

if st.button(t("run"), key="dashboard_refresh_run"):
    st.session_state[REPORT_KEY] = build_dashboard_refresh_package_from_text(workspace_id, proof_csv, history_csv, decision_csv)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("status", report.get("status", ""))
metrics[1].metric("rows", report.get("source_row_count", 0))
metrics[2].metric("events", report.get("unique_event_count", 0))
metrics[3].metric("wins", report.get("wins", 0))
metrics[4].metric("losses", report.get("losses", 0))
metrics[5].metric("win rate", report.get("win_rate_ex_push_cancel"))
metrics[6].metric("ROI", report.get("roi"))
metrics[7].metric("hash", _fragment(report.get("dashboard_refresh_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "dashboard_refresh_id": report.get("dashboard_refresh_id"),
    "dashboard_refresh_hash": report.get("dashboard_refresh_hash"),
    "status": report.get("status"),
    "review_reasons": report.get("review_reasons"),
    "source_row_count": report.get("source_row_count"),
    "history_row_count": report.get("history_row_count"),
    "decision_row_count": report.get("decision_row_count"),
    "unique_event_count": report.get("unique_event_count"),
    "duplicate_event_group_count": report.get("duplicate_event_group_count"),
    "completed_count": report.get("completed_count"),
    "pending_count": report.get("pending_count"),
    "wins": report.get("wins"),
    "losses": report.get("losses"),
    "pushes": report.get("pushes"),
    "cancels": report.get("cancels"),
    "win_rate_ex_push_cancel": report.get("win_rate_ex_push_cancel"),
    "total_profit_units": report.get("total_profit_units"),
    "stake_units": report.get("stake_units"),
    "roi": report.get("roi"),
    "average_CLV_decimal_delta": report.get("average_CLV_decimal_delta"),
    "average_baseline_EV": report.get("average_baseline_EV"),
    "average_calibrated_EV": report.get("average_calibrated_EV"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('rows')}")
st.dataframe(pd.DataFrame(report.get("dashboard_rows") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('actions')}")
st.dataframe(pd.DataFrame(report.get("action_breakdown") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('blockers')}")
st.dataframe(pd.DataFrame(report.get("blocker_breakdown") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('events')}")
st.dataframe(pd.DataFrame(report.get("event_breakdown") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('duplicates')}")
st.dataframe(pd.DataFrame(report.get("duplicate_event_groups") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('segments')}")
st.dataframe(pd.DataFrame(report.get("segment_breakdown") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('manifest')}")
st.json(report.get("manifest") or {})

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('dashboard_refresh_hash'))}"
st.download_button(t("download_json"), export_dashboard_refresh_json(report).encode("utf-8"), file_name=f"aba_dashboard_refresh_{suffix}.json", mime="application/json", key=f"dashboard_refresh_json_{safe_text(report.get('dashboard_refresh_hash'))}")
st.download_button(t("download_summary"), export_dashboard_summary_csv(report).encode("utf-8"), file_name=f"aba_dashboard_summary_{suffix}.csv", mime="text/csv", key=f"dashboard_refresh_summary_{safe_text(report.get('dashboard_refresh_hash'))}")
st.download_button(t("download_rows"), export_dashboard_rows_csv(report).encode("utf-8"), file_name=f"aba_dashboard_rows_{suffix}.csv", mime="text/csv", key=f"dashboard_refresh_rows_{safe_text(report.get('dashboard_refresh_hash'))}")
st.download_button(t("download_events"), export_event_breakdown_csv(report).encode("utf-8"), file_name=f"aba_dashboard_events_{suffix}.csv", mime="text/csv", key=f"dashboard_refresh_events_{safe_text(report.get('dashboard_refresh_hash'))}")
st.download_button(t("download_duplicates"), export_duplicate_groups_csv(report).encode("utf-8"), file_name=f"aba_dashboard_duplicates_{suffix}.csv", mime="text/csv", key=f"dashboard_refresh_duplicates_{safe_text(report.get('dashboard_refresh_hash'))}")
st.download_button(t("download_segments"), export_segment_breakdown_csv(report).encode("utf-8"), file_name=f"aba_dashboard_segments_{suffix}.csv", mime="text/csv", key=f"dashboard_refresh_segments_{safe_text(report.get('dashboard_refresh_hash'))}")
st.download_button(t("download_blockers"), export_blocker_breakdown_csv(report).encode("utf-8"), file_name=f"aba_dashboard_blockers_{suffix}.csv", mime="text/csv", key=f"dashboard_refresh_blockers_{safe_text(report.get('dashboard_refresh_hash'))}")
st.download_button(t("download_manifest"), export_dashboard_manifest_json(report).encode("utf-8"), file_name=f"aba_dashboard_manifest_{suffix}.json", mime="application/json", key=f"dashboard_refresh_manifest_{safe_text(report.get('dashboard_refresh_hash'))}")
