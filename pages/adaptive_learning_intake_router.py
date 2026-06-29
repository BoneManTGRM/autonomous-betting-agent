from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.adaptive_learning_intake_router import (
    LANES,
    build_adaptive_learning_intake_from_text,
    export_intake_manifest_json,
    lane_csv,
)
from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Adaptive Learning Intake Router", layout="wide")
LANG = render_app_sidebar("adaptive_learning_intake_router", language_key="adaptive_learning_intake_language")

REPORT_KEY = "adaptive_learning_intake_report"

TEXT = {
    "en": {
        "title": "Adaptive Learning Intake Router",
        "caption": "Route learning data into verified, review, shadow, or quarantine lanes without changing official records or live behavior.",
        "workspace_id": "Workspace ID",
        "package_json": "Offline package manifest JSON",
        "shadow_csv": "Optional shadow-learning CSV",
        "review_json": "Optional review rows JSON",
        "verified_confidence": "Verified confidence threshold",
        "review_confidence": "Review confidence threshold",
        "run": "Run intake router",
        "ready": "INTAKE READY",
        "review": "REVIEW REQUIRED",
        "empty": "NO ROWS",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "summary": "Intake summary",
        "verified": "Verified Lane",
        "review_lane": "Review Lane",
        "shadow": "Shadow Lane",
        "quarantine": "Quarantine Lane",
        "manifest": "Download intake manifest JSON",
        "lane_download": "Download lane CSV",
        "no_report": "Run the intake router to view lane outputs.",
    },
    "es": {
        "title": "Router Adaptativo de Intake Learning",
        "caption": "Rutea datos de learning a verified, review, shadow o quarantine sin cambiar registros oficiales ni comportamiento en vivo.",
        "workspace_id": "ID de workspace",
        "package_json": "JSON manifest del paquete offline",
        "shadow_csv": "CSV opcional para shadow learning",
        "review_json": "JSON opcional de filas para revision",
        "verified_confidence": "Umbral de confianza verified",
        "review_confidence": "Umbral de confianza review",
        "run": "Ejecutar router intake",
        "ready": "INTAKE READY",
        "review": "REVIEW REQUIRED",
        "empty": "NO ROWS",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "summary": "Resumen intake",
        "verified": "Verified Lane",
        "review_lane": "Review Lane",
        "shadow": "Shadow Lane",
        "quarantine": "Quarantine Lane",
        "manifest": "Descargar manifest JSON intake",
        "lane_download": "Descargar CSV de lane",
        "no_report": "Ejecuta el router intake para ver outputs por lane.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "intake"


def _flat_rows(rows):
    output = []
    for row in rows or []:
        if isinstance(row, dict):
            output.append({key: value for key, value in row.items() if key != "raw_row"})
    return output


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="adaptive_intake_workspace_id"))

cols = st.columns(2)
verified_confidence = cols[0].number_input(t("verified_confidence"), min_value=0.50, max_value=1.0, value=0.82, step=0.01, key="adaptive_verified_confidence")
review_confidence = cols[1].number_input(t("review_confidence"), min_value=0.10, max_value=0.95, value=0.50, step=0.01, key="adaptive_review_confidence")

package_json = st.text_area(t("package_json"), value="", key="adaptive_package_json", height=180)
shadow_csv = st.text_area(t("shadow_csv"), value="", key="adaptive_shadow_csv", height=140)
review_json = st.text_area(t("review_json"), value="", key="adaptive_review_json", height=140)

if st.button(t("run"), key="adaptive_intake_run"):
    st.session_state[REPORT_KEY] = build_adaptive_learning_intake_from_text(
        workspace_id,
        package_json,
        shadow_csv,
        review_json,
        verified_confidence=float(verified_confidence),
        review_confidence=float(review_confidence),
    )

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

status = safe_text(report.get("status"))
status_key = "ready" if status == "INTAKE READY" else "empty" if status == "NO ROWS" else "review"
st.write({t(status_key): True, t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0})

metrics = st.columns(7)
metrics[0].metric("status", status)
metrics[1].metric("total", report.get("total_rows", 0))
metrics[2].metric("verified", report.get("verified_count", 0))
metrics[3].metric("review", report.get("review_count", 0))
metrics[4].metric("shadow", report.get("shadow_count", 0))
metrics[5].metric("quarantine", report.get("quarantine_count", 0))
metrics[6].metric("hash", _fragment(report.get("intake_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "intake_id": report.get("intake_id"),
    "intake_hash": report.get("intake_hash"),
    "status": report.get("status"),
    "total_rows": report.get("total_rows"),
    "verified_count": report.get("verified_count"),
    "review_count": report.get("review_count"),
    "shadow_count": report.get("shadow_count"),
    "quarantine_count": report.get("quarantine_count"),
    "official_metrics_row_count": report.get("official_metrics_row_count"),
    "shadow_learning_row_count": report.get("shadow_learning_row_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
})

lane_titles = {
    "VERIFIED LANE": t("verified"),
    "REVIEW LANE": t("review_lane"),
    "SHADOW LANE": t("shadow"),
    "QUARANTINE LANE": t("quarantine"),
}
for lane in LANES:
    st.markdown(f"### {lane_titles.get(lane, lane)}")
    rows = _flat_rows((report.get("lane_rows") or {}).get(lane) or [])
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.download_button(
        f"{t('lane_download')}: {lane}",
        lane_csv(report, lane).encode("utf-8"),
        file_name=f"aba_adaptive_intake_{safe_text(report.get('workspace_id'))}_{safe_text(lane).lower().replace(' ', '_')}_{_fragment(report.get('intake_hash'))}.csv",
        mime="text/csv",
        key=f"adaptive_intake_{safe_text(lane)}_{safe_text(report.get('intake_hash'))}",
    )

st.download_button(
    t("manifest"),
    export_intake_manifest_json(report).encode("utf-8"),
    file_name=f"aba_adaptive_intake_manifest_{safe_text(report.get('workspace_id'))}_{_fragment(report.get('intake_hash'))}.json",
    mime="application/json",
    key=f"adaptive_intake_manifest_{safe_text(report.get('intake_hash'))}",
)
