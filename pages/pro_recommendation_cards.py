from __future__ import annotations

import json

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

st.set_page_config(page_title="Recommendation Cards", layout="wide")
LANG = render_app_sidebar("pro_recommendation_cards", language_key="pro_recommendation_cards_language")

REPORT_KEY = "pro_recommendation_cards_report"

TEXT = {
    "en": {
        "title": "Recommendation Cards",
        "caption": "Create clean report cards from the Market Optimizer result.",
        "help": "Run Market Optimizer first. This page will use that result automatically. Manual paste boxes are under Advanced.",
        "workspace_id": "Workspace ID",
        "source": "Source check",
        "run": "Build cards",
        "advanced": "Advanced manual input",
        "optimizer_json": "Manual Market Optimizer JSON",
        "market_csv": "Optional Market Hunter rows CSV",
        "chain_csv": "Optional Chain Builder rows CSV",
        "context_csv": "Optional sports context CSV",
        "summary": "Summary",
        "cards": "Cards",
        "pro": "Pro view",
        "checks": "Checks",
        "safety": "Safety details",
        "no_report": "Build cards to view outputs.",
        "no_source": "No Market Optimizer result found. Run Market Optimizer first or paste JSON in Advanced.",
    },
    "es": {
        "title": "Tarjetas de Recomendación",
        "caption": "Crea tarjetas limpias desde Market Optimizer.",
        "help": "Ejecuta Market Optimizer primero. Esta página usa ese resultado automáticamente. Los campos manuales están en Avanzado.",
        "workspace_id": "ID de workspace",
        "source": "Revisión de fuente",
        "run": "Construir tarjetas",
        "advanced": "Entrada manual avanzada",
        "optimizer_json": "JSON manual de Market Optimizer",
        "market_csv": "CSV opcional Market Hunter",
        "chain_csv": "CSV opcional Chain Builder",
        "context_csv": "CSV opcional contexto deportivo",
        "summary": "Resumen",
        "cards": "Tarjetas",
        "pro": "Vista Pro",
        "checks": "Checks",
        "safety": "Detalles de seguridad",
        "no_report": "Construye tarjetas para ver outputs.",
        "no_source": "No hay resultado de Market Optimizer. Ejecútalo primero o pega JSON en Avanzado.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "cards"


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

workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="pro_cards_workspace_id"))
auto_optimizer_json, optimizer_found = _session_json("market_optimizer_preview_report")

st.subheader(t("source"))
cols = st.columns(2)
cols[0].metric("Market Optimizer result", "found" if optimizer_found else "missing")
cols[1].metric("workspace", workspace_id)
if not optimizer_found:
    st.warning(t("no_source"))

with st.expander(t("advanced"), expanded=False):
    optimizer_json = st.text_area(t("optimizer_json"), value=auto_optimizer_json, key="pro_cards_optimizer_json", height=220)
    market_csv = st.text_area(t("market_csv"), value="", key="pro_cards_market_csv", height=120)
    chain_csv = st.text_area(t("chain_csv"), value="", key="pro_cards_chain_csv", height=120)
    context_csv = st.text_area(t("context_csv"), value="", key="pro_cards_context_csv", height=120)

if st.button(t("run"), key="pro_cards_run", type="primary"):
    st.session_state[REPORT_KEY] = build_pro_recommendation_cards_from_text(workspace_id, optimizer_json or auto_optimizer_json, market_csv, chain_csv, context_csv)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

metrics = st.columns(7)
metrics[0].metric("status", report.get("cards_status", ""))
metrics[1].metric("cards", report.get("card_count", 0))
metrics[2].metric("bet", report.get("bet_count", 0))
metrics[3].metric("watch", report.get("watch_count", 0))
metrics[4].metric("avoid", report.get("avoid_count", 0))
metrics[5].metric("warn", report.get("warn_count", 0))
metrics[6].metric("fail", report.get("fail_count", 0))

tabs = st.tabs([t("summary"), t("cards"), t("pro"), t("checks")])
with tabs[0]:
    st.json({
        "workspace_id": report.get("workspace_id"),
        "cards_status": report.get("cards_status"),
        "card_count": report.get("card_count"),
        "bet_count": report.get("bet_count"),
        "watch_count": report.get("watch_count"),
        "avoid_count": report.get("avoid_count"),
        "preview_only": report.get("preview_only"),
        "live_changes": report.get("live_changes"),
    })
with tabs[1]:
    st.dataframe(pd.DataFrame(report.get("recommendation_cards") or []), use_container_width=True, hide_index=True)
with tabs[2]:
    st.json(report.get("marco_cards") or [])
with tabs[3]:
    st.dataframe(pd.DataFrame(report.get("completion_checks") or []), use_container_width=True, hide_index=True)

with st.expander(t("safety"), expanded=False):
    st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('cards_hash'))}"
st.download_button("Download cards JSON", export_recommendation_cards_json(report).encode("utf-8"), file_name=f"aba_recommendation_cards_{suffix}.json", mime="application/json", key=f"pro_cards_json_{safe_text(report.get('cards_hash'))}")
st.download_button("Download cards CSV", export_recommendation_cards_csv(report).encode("utf-8"), file_name=f"aba_recommendation_cards_{suffix}.csv", mime="text/csv", key=f"pro_cards_csv_{safe_text(report.get('cards_hash'))}")
st.download_button("Download pro view JSON", export_marco_cards_json(report).encode("utf-8"), file_name=f"aba_pro_cards_{suffix}.json", mime="application/json", key=f"pro_cards_marco_{safe_text(report.get('cards_hash'))}")
st.download_button("Download checks CSV", export_completion_checks_csv(report).encode("utf-8"), file_name=f"aba_recommendation_card_checks_{suffix}.csv", mime="text/csv", key=f"pro_cards_checks_{safe_text(report.get('cards_hash'))}")
st.download_button("Download manifest JSON", export_recommendation_manifest_json(report).encode("utf-8"), file_name=f"aba_recommendation_card_manifest_{suffix}.json", mime="application/json", key=f"pro_cards_manifest_{safe_text(report.get('cards_hash'))}")
