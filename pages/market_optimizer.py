from __future__ import annotations

import pandas as pd
import streamlit as st

from autonomous_betting_agent.commercial_platform_tools import normalize_workspace_id
from autonomous_betting_agent.market_optimizer_preview import (
    build_market_optimizer_preview_from_text,
    export_avoid_list_csv,
    export_best_books_csv,
    export_chain_builder_csv,
    export_marco_mode_json,
    export_market_hunter_csv,
    export_market_optimizer_json,
    export_market_optimizer_manifest_json,
)
from autonomous_betting_agent.row_normalizer import safe_text
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title="Market Optimizer", layout="wide")
LANG = render_app_sidebar("market_optimizer", language_key="market_optimizer_language")

REPORT_KEY = "market_optimizer_preview_report"
ROW_SOURCE_KEYS = ["odds_lock_pro_candidate_rows", "pro_predictor_latest_rows", "fresh_odds_slate_builder_rows"]
HISTORY_SOURCE_KEYS = ["odds_lock_pro_locked_rows", "public_proof_dashboard_refresh_rows"]

TEXT = {
    "en": {
        "title": "Market Optimizer",
        "caption": "Turns the latest rows into Play / Watch / Avoid lists and compares sportsbook prices. Most users should run Pro Predictor first, then use this page only when they want a deeper market preview.",
        "how": "How to use this page",
        "how_text": "Normally you do not type or paste anything here. Run Pro Predictor or Odds Lock Pro first, then press Run optimizer preview. Manual CSV boxes are hidden under Advanced.",
        "workspace_id": "Workspace ID",
        "bankroll": "Preview bankroll units",
        "auto_source": "Automatic source check",
        "run": "Run optimizer preview",
        "advanced": "Advanced manual input — usually leave closed",
        "market_csv": "Manual market / sportsbook rows CSV",
        "history_csv": "Optional manual proof/history rows CSV",
        "summary": "Optimizer summary",
        "hunter": "Playable / watch rows",
        "books": "Best-book comparison",
        "chains": "Chain preview",
        "avoid": "Avoid list",
        "marco": "Pro view JSON",
        "safety": "Safety details",
        "download_json": "Download optimizer JSON",
        "download_hunter": "Download playable rows CSV",
        "download_books": "Download book comparison CSV",
        "download_chains": "Download chain preview CSV",
        "download_avoid": "Download avoid list CSV",
        "download_marco": "Download pro view JSON",
        "download_manifest": "Download manifest JSON",
        "no_report": "Run the optimizer preview to view outputs.",
        "no_source": "No current rows found yet. Go to Pro Predictor or Odds Lock Pro first, then return here.",
    },
    "es": {
        "title": "Optimizador de Mercado",
        "caption": "Convierte las filas recientes en listas de jugar / observar / evitar y compara precios de sportsbook. Normalmente usa Predictor Pro primero.",
        "how": "Cómo usar esta página",
        "how_text": "Normalmente no escribes ni pegas nada aquí. Ejecuta Predictor Pro u Odds Lock Pro primero y luego presiona Ejecutar optimizer preview. Los CSV manuales están en Avanzado.",
        "workspace_id": "ID de workspace",
        "bankroll": "Bankroll preview units",
        "auto_source": "Revisión de fuente automática",
        "run": "Ejecutar optimizer preview",
        "advanced": "Entrada manual avanzada — normalmente dejar cerrado",
        "market_csv": "CSV manual de mercado / sportsbook",
        "history_csv": "CSV manual opcional de prueba/historial",
        "summary": "Resumen optimizer",
        "hunter": "Filas jugar / observar",
        "books": "Comparación best-book",
        "chains": "Chain preview",
        "avoid": "Avoid list",
        "marco": "JSON pro view",
        "safety": "Detalles de seguridad",
        "download_json": "Descargar JSON optimizer",
        "download_hunter": "Descargar CSV jugables",
        "download_books": "Descargar CSV comparación libros",
        "download_chains": "Descargar CSV chain preview",
        "download_avoid": "Descargar CSV avoid list",
        "download_marco": "Descargar JSON pro view",
        "download_manifest": "Descargar JSON manifest",
        "no_report": "Ejecuta el optimizer preview para ver outputs.",
        "no_source": "No hay filas actuales todavía. Ve a Predictor Pro u Odds Lock Pro primero y regresa aquí.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, key)


def _fragment(value: str | None) -> str:
    return safe_text(value).split("_")[-1][:12] or "optimizer"


def _session_rows_to_csv(keys: list[str]) -> tuple[str, str, int]:
    for key in keys:
        value = st.session_state.get(key)
        if value is None:
            continue
        try:
            frame = pd.DataFrame(value)
        except Exception:
            frame = pd.DataFrame()
        if not frame.empty:
            return frame.to_csv(index=False), key, int(len(frame))
    return "", "", 0


st.title(t("title"))
st.caption(t("caption"))
st.info(f"**{t('how')}** — {t('how_text')}")

workspace_id = normalize_workspace_id(st.text_input(t("workspace_id"), value=st.session_state.get("aba_test_window_id", "test_01"), key="market_optimizer_workspace_id"))
bankroll = st.number_input(t("bankroll"), min_value=1.0, value=1000.0, step=50.0, key="market_optimizer_bankroll")

auto_market_csv, market_source, market_count = _session_rows_to_csv(ROW_SOURCE_KEYS)
auto_history_csv, history_source, history_count = _session_rows_to_csv(HISTORY_SOURCE_KEYS)

st.subheader(t("auto_source"))
cols = st.columns(3)
cols[0].metric("market rows found", market_count)
cols[1].metric("history rows found", history_count)
cols[2].metric("source", market_source or "none")
if market_count <= 0:
    st.warning(t("no_source"))

with st.expander(t("advanced"), expanded=False):
    market_csv = st.text_area(t("market_csv"), value=auto_market_csv, key="market_optimizer_market_csv", height=220)
    history_csv = st.text_area(t("history_csv"), value=auto_history_csv, key="market_optimizer_history_csv", height=160)

if st.button(t("run"), key="market_optimizer_run", type="primary"):
    st.session_state[REPORT_KEY] = build_market_optimizer_preview_from_text(workspace_id, market_csv or auto_market_csv, history_csv or auto_history_csv, bankroll)

report = st.session_state.get(REPORT_KEY, {})
if not report:
    st.info(t("no_report"))
    st.stop()

metrics = st.columns(8)
metrics[0].metric("markets", report.get("market_row_count", 0))
metrics[1].metric("playable", report.get("playable_count", 0))
metrics[2].metric("watch", report.get("watch_count", 0))
metrics[3].metric("wait", report.get("wait_count", 0))
metrics[4].metric("no bet", report.get("no_play_count", 0))
metrics[5].metric("low risk", report.get("low_risk_count", 0))
metrics[6].metric("high risk", report.get("high_risk_count", 0))
metrics[7].metric("hash", _fragment(report.get("optimizer_hash")))

tabs = st.tabs([t("summary"), t("hunter"), t("books"), t("chains"), t("avoid"), t("marco")])
with tabs[0]:
    st.json({
        "workspace_id": report.get("workspace_id"),
        "market_row_count": report.get("market_row_count"),
        "history_row_count": report.get("history_row_count"),
        "playable_count": report.get("playable_count"),
        "watch_count": report.get("watch_count"),
        "wait_count": report.get("wait_count"),
        "no_play_count": report.get("no_play_count"),
        "preview_only": report.get("preview_only"),
        "live_changes": report.get("live_changes"),
    })
with tabs[1]:
    st.dataframe(pd.DataFrame(report.get("market_hunter_rows") or []), use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(pd.DataFrame(report.get("best_book_rows") or []), use_container_width=True, hide_index=True)
with tabs[3]:
    st.dataframe(pd.DataFrame(report.get("chain_builder_rows") or []), use_container_width=True, hide_index=True)
with tabs[4]:
    st.dataframe(pd.DataFrame(report.get("avoid_list") or []), use_container_width=True, hide_index=True)
with tabs[5]:
    st.json(report.get("marco_mode") or {})

with st.expander(t("safety"), expanded=False):
    st.json(report.get("safety_gates") or {})

suffix = f"{safe_text(report.get('workspace_id'))}_{_fragment(report.get('optimizer_hash'))}"
st.download_button(t("download_json"), export_market_optimizer_json(report).encode("utf-8"), file_name=f"aba_market_optimizer_{suffix}.json", mime="application/json", key=f"market_optimizer_json_{safe_text(report.get('optimizer_hash'))}")
st.download_button(t("download_hunter"), export_market_hunter_csv(report).encode("utf-8"), file_name=f"aba_market_hunter_{suffix}.csv", mime="text/csv", key=f"market_hunter_csv_{safe_text(report.get('optimizer_hash'))}")
st.download_button(t("download_books"), export_best_books_csv(report).encode("utf-8"), file_name=f"aba_best_books_{suffix}.csv", mime="text/csv", key=f"market_books_csv_{safe_text(report.get('optimizer_hash'))}")
st.download_button(t("download_chains"), export_chain_builder_csv(report).encode("utf-8"), file_name=f"aba_chain_builder_{suffix}.csv", mime="text/csv", key=f"market_chains_csv_{safe_text(report.get('optimizer_hash'))}")
st.download_button(t("download_avoid"), export_avoid_list_csv(report).encode("utf-8"), file_name=f"aba_avoid_list_{suffix}.csv", mime="text/csv", key=f"market_avoid_csv_{safe_text(report.get('optimizer_hash'))}")
st.download_button(t("download_marco"), export_marco_mode_json(report).encode("utf-8"), file_name=f"aba_marco_mode_{suffix}.json", mime="application/json", key=f"market_marco_json_{safe_text(report.get('optimizer_hash'))}")
st.download_button(t("download_manifest"), export_market_optimizer_manifest_json(report).encode("utf-8"), file_name=f"aba_market_optimizer_manifest_{suffix}.json", mime="application/json", key=f"market_manifest_json_{safe_text(report.get('optimizer_hash'))}")
