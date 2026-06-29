from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.reparodynamics_shadow_scoring import (
    build_reparodynamics_shadow_scoring_report_from_text,
    export_scored_candidates_csv,
    export_shadow_scoring_json,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Reparodynamics Shadow Scoring", layout="wide")
LANG = render_app_sidebar("reparodynamics_shadow_scoring", language_key="reparodynamics_shadow_scoring_language")

REPORT_KEY = "reparodynamics_shadow_scoring_report"

TEXT = {
    "en": {
        "title": "Reparodynamics Shadow Scoring",
        "caption": "Score repair candidates using shadow-only RYE-style benefit, risk, evidence, ROI, CLV, calibration, and overfit checks.",
        "workspace_id": "Workspace ID",
        "dynamic_report": "Dynamic/Reparodynamics report JSON",
        "odds_report": "Optional odds math report JSON",
        "operator_csv": "Optional operator candidate CSV",
        "run": "Run shadow scoring",
        "summary": "Shadow scoring summary",
        "candidates": "Scored candidates",
        "safety": "Safety gates",
        "download_json": "Download shadow scoring JSON",
        "download_csv": "Download candidates CSV",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Run shadow scoring to view outputs.",
    },
    "es": {
        "title": "Reparodynamics Shadow Scoring",
        "caption": "Califica repair candidates en shadow-only con beneficio, riesgo, evidencia, ROI, CLV, calibración y overfit.",
        "workspace_id": "ID de workspace",
        "dynamic_report": "JSON de reporte Dynamic/Reparodynamics",
        "odds_report": "JSON opcional de odds math",
        "operator_csv": "CSV opcional de candidate operador",
        "run": "Ejecutar shadow scoring",
        "summary": "Resumen shadow scoring",
        "candidates": "Candidates calificados",
        "safety": "Safety gates",
        "download_json": "Descargar JSON shadow scoring",
        "download_csv": "Descargar CSV candidates",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Ejecuta shadow scoring para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "shadow"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="shadow_scoring_workspace_id"))

dynamic_report = st.text_area(t("dynamic_report"), value="", key="shadow_scoring_dynamic_report", height=200)
odds_report = st.text_area(t("odds_report"), value="", key="shadow_scoring_odds_report", height=160)
operator_csv = st.text_area(t("operator_csv"), value="", key="shadow_scoring_operator_csv", height=120)

if st.button(t("run"), key="shadow_scoring_run"):
    st.session_state[REPORT_KEY] = build_reparodynamics_shadow_scoring_report_from_text(
        workspace_id,
        dynamic_report,
        odds_report,
        operator_csv,
    )

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(7)
metrics[0].metric("status", report.get("status", ""))
metrics[1].metric("candidates", report.get("candidate_count", 0))
metrics[2].metric("manual", report.get("manual_review_count", 0))
metrics[3].metric("rejected", report.get("rejected_count", 0))
metrics[4].metric("blocked", report.get("data_blocked_count", 0))
metrics[5].metric("keep", report.get("keep_testing_count", 0))
metrics[6].metric("hash", _fragment(report.get("shadow_scoring_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "shadow_scoring_id": report.get("shadow_scoring_id"),
    "shadow_scoring_hash": report.get("shadow_scoring_hash"),
    "status": report.get("status"),
    "mode": report.get("mode"),
    "candidate_count": report.get("candidate_count"),
    "manual_review_count": report.get("manual_review_count"),
    "rejected_count": report.get("rejected_count"),
    "data_blocked_count": report.get("data_blocked_count"),
    "keep_testing_count": report.get("keep_testing_count"),
    "average_RYE_score": report.get("average_RYE_score"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

st.markdown(f"### {t('candidates')}")
st.dataframe(pd.DataFrame(report.get("scored_candidates") or []), use_container_width=True, hide_index=True)

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('shadow_scoring_hash'))}"
st.download_button(t("download_json"), export_shadow_scoring_json(report).encode("utf-8"), file_name=f"aba_reparodynamics_shadow_scoring_{suffix}.json", mime="application/json", key=f"shadow_scoring_json_{safe_text(report.get('shadow_scoring_hash'))}")
st.download_button(t("download_csv"), export_scored_candidates_csv(report).encode("utf-8"), file_name=f"aba_reparodynamics_shadow_candidates_{suffix}.csv", mime="text/csv", key=f"shadow_scoring_csv_{safe_text(report.get('shadow_scoring_hash'))}")
