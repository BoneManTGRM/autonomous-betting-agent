from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.pro_recommendation_cards import (
    build_pro_recommendation_cards_from_text,
    export_completion_checks_csv,
    export_marco_cards_json,
    export_recommendation_cards_csv,
    export_recommendation_cards_json,
    export_recommendation_manifest_json,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Pro Recommendation Cards", layout="wide")
LANG = render_app_sidebar("pro_recommendation_cards", language_key="pro_recommendation_cards_language")

REPORT_KEY = "pro_recommendation_cards_report"

TEXT = {
    "en": {
        "title": "Pro Recommendation Cards",
        "caption": "Build the final #51 pro-bettor recommendation format from Market Optimizer output and optional sports context rows.",
        "workspace_id": "Workspace ID",
        "optimizer_json": "Market Optimizer JSON",
        "market_csv": "Optional Market Hunter rows CSV override",
        "chain_csv": "Optional Chain Builder rows CSV override",
        "context_csv": "Optional sports analysis context CSV",
        "run": "Build recommendation cards",
        "summary": "Cards summary",
        "cards": "Recommendation cards",
        "marco": "Marco-safe cards",
        "checks": "Completion checks",
        "safety": "Safety gates",
        "download_json": "Download cards JSON",
        "download_csv": "Download cards CSV",
        "download_marco": "Download Marco cards JSON",
        "download_checks": "Download checks CSV",
        "download_manifest": "Download manifest JSON",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Build recommendation cards to view outputs.",
    },
    "es": {
        "title": "Pro Recommendation Cards",
        "caption": "Construye el formato final pro-bettor #51 desde Market Optimizer y contexto deportivo opcional.",
        "workspace_id": "ID de workspace",
        "optimizer_json": "JSON Market Optimizer",
        "market_csv": "CSV Market Hunter opcional",
        "chain_csv": "CSV Chain Builder opcional",
        "context_csv": "CSV contexto deportivo opcional",
        "run": "Construir recommendation cards",
        "summary": "Resumen cards",
        "cards": "Recommendation cards",
        "marco": "Marco-safe cards",
        "checks": "Completion checks",
        "safety": "Safety gates",
        "download_json": "Descargar JSON cards",
        "download_csv": "Descargar CSV cards",
        "download_marco": "Descargar JSON Marco cards",
        "download_checks": "Descargar CSV checks",
        "download_manifest": "Descargar JSON manifest",
        "preview_only": "PREVIEW ONLY",
        "no_files": "NO FILES WRITTEN",
        "no_live": "NO LIVE CHANGES",
        "no_report": "Construye recommendation cards para ver outputs.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "cards"


st.title(t("title"))
st.caption(t("caption"))
workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="pro_cards_workspace_id"))
optimizer_json = st.text_area(t("optimizer_json"), value="", key="pro_cards_optimizer_json", height=220)
market_csv = st.text_area(t("market_csv"), value="", key="pro_cards_market_csv", height=140)
chain_csv = st.text_area(t("chain_csv"), value="", key="pro_cards_chain_csv", height=120)
context_csv = st.text_area(t("context_csv"), value="", key="pro_cards_context_csv", height=160)

if st.button(t("run"), key="pro_cards_run"):
    st.session_state[REPORT_KEY] = build_pro_recommendation_cards_from_text(workspace_id, optimizer_json, market_csv, chain_csv, context_csv)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

st.write({t("preview_only"): bool(report.get("preview_only")), t("no_files"): int(report.get("files_written") or 0) == 0, t("no_live"): int(report.get("live_changes") or 0) == 0})
metrics = st.columns(8)
metrics[0].metric("status", report.get("cards_status", ""))
metrics[1].metric("cards", report.get("card_count", 0))
metrics[2].metric("bet", report.get("bet_count", 0))
metrics[3].metric("watch", report.get("watch_count", 0))
metrics[4].metric("avoid", report.get("avoid_count", 0))
metrics[5].metric("warn", report.get("warn_count", 0))
metrics[6].metric("fail", report.get("fail_count", 0))
metrics[7].metric("hash", _fragment(report.get("cards_hash")))

st.markdown(f"### {t('summary')}")
st.json({
    "schema_version": report.get("schema_version"),
    "workspace_id": report.get("workspace_id"),
    "cards_id": report.get("cards_id"),
    "cards_hash": report.get("cards_hash"),
    "mode": report.get("mode"),
    "cards_status": report.get("cards_status"),
    "card_count": report.get("card_count"),
    "bet_count": report.get("bet_count"),
    "watch_count": report.get("watch_count"),
    "avoid_count": report.get("avoid_count"),
    "pass_count": report.get("pass_count"),
    "warn_count": report.get("warn_count"),
    "fail_count": report.get("fail_count"),
    "preview_only": report.get("preview_only"),
    "files_written": report.get("files_written"),
    "live_changes": report.get("live_changes"),
})

st.markdown(f"### {t('cards')}")
st.dataframe(pd.DataFrame(report.get("recommendation_cards") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('marco')}")
st.json(report.get("marco_cards") or [])

st.markdown(f"### {t('checks')}")
st.dataframe(pd.DataFrame(report.get("completion_checks") or []), use_container_width=True, hide_index=True)

st.markdown(f"### {t('safety')}")
st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('cards_hash'))}"
st.download_button(t("download_json"), export_recommendation_cards_json(report).encode("utf-8"), file_name=f"aba_recommendation_cards_{suffix}.json", mime="application/json", key=f"pro_cards_json_{safe_text(report.get('cards_hash'))}")
st.download_button(t("download_csv"), export_recommendation_cards_csv(report).encode("utf-8"), file_name=f"aba_recommendation_cards_{suffix}.csv", mime="text/csv", key=f"pro_cards_csv_{safe_text(report.get('cards_hash'))}")
st.download_button(t("download_marco"), export_marco_cards_json(report).encode("utf-8"), file_name=f"aba_marco_cards_{suffix}.json", mime="application/json", key=f"pro_cards_marco_{safe_text(report.get('cards_hash'))}")
st.download_button(t("download_checks"), export_completion_checks_csv(report).encode("utf-8"), file_name=f"aba_recommendation_card_checks_{suffix}.csv", mime="text/csv", key=f"pro_cards_checks_{safe_text(report.get('cards_hash'))}")
st.download_button(t("download_manifest"), export_recommendation_manifest_json(report).encode("utf-8"), file_name=f"aba_recommendation_card_manifest_{suffix}.json", mime="application/json", key=f"pro_cards_manifest_{safe_text(report.get('cards_hash'))}")
