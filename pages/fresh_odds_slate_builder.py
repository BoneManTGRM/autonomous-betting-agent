from __future__ import annotations

import base64
import html
import json
import os
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.fresh_odds_slate_builder import (
    build_slate_rows_from_payload,
    fetch_the_odds_api_payload,
    normalize_the_odds_api_events,
    slate_builder_report_section,
    slate_builder_summary,
)
from autonomous_betting_agent.pick_hold_store import save_held_rows
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe

st.set_page_config(page_title="Fresh Odds Slate Builder", layout="wide")
LANG = render_app_sidebar("fresh_odds_slate_builder", language_key="fresh_odds_slate_builder_language", selector="radio")

SPORT_PRESETS = {
    "NBA": {"sport_key": "basketball_nba", "regions": "us", "markets": "h2h,spreads,totals"},
    "WNBA": {"sport_key": "basketball_wnba", "regions": "us", "markets": "h2h,spreads,totals"},
    "MLB": {"sport_key": "baseball_mlb", "regions": "us", "markets": "h2h,spreads,totals"},
    "NFL": {"sport_key": "americanfootball_nfl", "regions": "us", "markets": "h2h,spreads,totals"},
    "NHL": {"sport_key": "icehockey_nhl", "regions": "us", "markets": "h2h,spreads,totals"},
    "EPL Soccer": {"sport_key": "soccer_epl", "regions": "us,uk,eu", "markets": "h2h,spreads,totals"},
}
MARKET_LABELS = {"Moneyline / winner": "h2h", "Spread / handicap": "spreads", "Game total": "totals"}

TEXT = {
    "en": {
        "title": "Fresh Odds Slate Builder",
        "caption": "Build a fresh sportsbook slate and send ready rows forward.",
        "quick_start": "Choose sport and markets, fetch odds, or upload the Pro Predictor CSV. Then send ready rows forward.",
        "fetch": "Fresh odds fetch",
        "sport_preset": "Sport",
        "bet_types": "Bet types to include",
        "fetch_button": "Fetch odds for selected sport",
        "missing_key": "ODDS_API_KEY or THE_ODDS_API_KEY is not configured in Streamlit secrets.",
        "advanced_fetch": "Advanced API settings — usually leave closed",
        "sport_key": "Custom The Odds API sport key",
        "regions": "Regions",
        "markets": "Raw markets string",
        "bookmakers": "Bookmaker filter — optional",
        "csv_import": "Import Pro Predictor CSV",
        "csv_upload": "Upload Pro Predictor CSV",
        "csv_loaded": "CSV rows loaded and sent forward.",
        "manual": "Advanced: import raw API JSON — usually skip",
        "upload": "Upload JSON from an API response",
        "api_name": "API payload type",
        "summary": "Slate summary",
        "rows": "All generated rows",
        "ready": "Ready rows to send forward",
        "missing": "Rows needing review",
        "report": "Technical report — optional",
        "send": "Send ready rows forward",
        "sent": "Ready rows were copied to the next-step session.",
        "download": "Download slate CSV",
        "empty_rows": "No rows yet. Fetch odds, upload CSV, or import JSON first.",
    },
    "es": {
        "title": "Constructor de Slate de Odds Frescas",
        "caption": "Construye un slate fresco y envia filas listas.",
        "quick_start": "Elige deporte y mercados, consulta momios, o sube el CSV de Predictor Pro. Luego envia filas listas.",
        "fetch": "Consulta de momios frescos",
        "sport_preset": "Deporte",
        "bet_types": "Tipos de apuesta a incluir",
        "fetch_button": "Consultar momios del deporte seleccionado",
        "missing_key": "ODDS_API_KEY o THE_ODDS_API_KEY no esta configurada en Streamlit secrets.",
        "advanced_fetch": "Configuracion API avanzada — normalmente dejar cerrado",
        "sport_key": "Clave personalizada The Odds API",
        "regions": "Regiones",
        "markets": "Texto raw de mercados",
        "bookmakers": "Filtro bookmaker — opcional",
        "csv_import": "Importar CSV de Predictor Pro",
        "csv_upload": "Subir CSV de Predictor Pro",
        "csv_loaded": "Filas CSV cargadas y enviadas.",
        "manual": "Avanzado: importar JSON raw — normalmente omitir",
        "upload": "Subir JSON de una respuesta API",
        "api_name": "Tipo de payload API",
        "summary": "Resumen del slate",
        "rows": "Todas las filas generadas",
        "ready": "Filas listas para enviar",
        "missing": "Filas para revisar",
        "report": "Reporte tecnico — opcional",
        "send": "Enviar filas listas",
        "sent": "Las filas listas fueron copiadas a la siguiente sesion.",
        "download": "Descargar CSV de slate",
        "empty_rows": "Aun no hay filas. Consulta momios, sube CSV o importa JSON primero.",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, TEXT["en"].get(key, key))


def display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return localize_dataframe(frame, LANG)


def csv_link(label: str, frame: pd.DataFrame, filename: str) -> None:
    data = base64.b64encode(frame.to_csv(index=False).encode("utf-8")).decode("ascii")
    st.markdown(f'<a href="data:text/csv;base64,{data}" download="{html.escape(filename)}" style="display:block;text-align:center;background:#ef5350;color:white;padding:.75rem 1rem;border-radius:.45rem;text-decoration:none;font-weight:700;">{html.escape(label)}</a>', unsafe_allow_html=True)


def show_table(title: str, frame: pd.DataFrame) -> None:
    st.subheader(title)
    st.info(t("empty_rows")) if frame.empty else st.dataframe(display_frame(frame), use_container_width=True, hide_index=True)


def get_secret(*names: str) -> str:
    for name in names:
        try:
            value = str(st.secrets.get(name, "") or "").strip()
            if value:
                return value
        except Exception:
            pass
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _load_json_upload(upload: Any) -> Any:
    return None if upload is None else json.loads(upload.read().decode("utf-8"))


def _selected_markets(labels: list[str]) -> str:
    values = [MARKET_LABELS[label] for label in labels if label in MARKET_LABELS]
    return ",".join(values) or "h2h"


def _current_fetch_settings() -> tuple[str, str, str, str]:
    preset = st.session_state.get("fosb_sport_preset") or "NBA"
    defaults = SPORT_PRESETS.get(str(preset), SPORT_PRESETS["NBA"])
    return (
        str(st.session_state.get("fosb_custom_sport_key") or defaults["sport_key"]).strip(),
        str(st.session_state.get("fosb_regions") or defaults["regions"]).strip(),
        str(st.session_state.get("fosb_markets") or defaults["markets"]).strip(),
        str(st.session_state.get("fosb_bookmakers") or "").strip(),
    )


def _ready_csv_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    out = frame.copy().fillna("")
    if "decimal_odds" not in out.columns and "decimal_price" in out.columns:
        out["decimal_odds"] = out["decimal_price"]
    if "decimal_price" not in out.columns and "decimal_odds" in out.columns:
        out["decimal_price"] = out["decimal_odds"]
    if "market" not in out.columns and "market_type" in out.columns:
        out["market"] = out["market_type"]
    if "market_type" not in out.columns and "market" in out.columns:
        out["market_type"] = out["market"]
    if "selection" not in out.columns and "prediction" in out.columns:
        out["selection"] = out["prediction"]
    if "prediction" not in out.columns and "selection" in out.columns:
        out["prediction"] = out["selection"]
    if "bookmaker" not in out.columns:
        out["bookmaker"] = out.get("sportsbook", "imported_csv")
    out["slate_builder_source"] = "pro_predictor_csv_import"
    out["slate_builder_generated_at"] = pd.Timestamp.utcnow().isoformat()
    out["slate_builder_api_name"] = out.get("odds_source", "Pro Predictor CSV")
    out["slate_builder_ready_for_advisory_pipeline"] = True
    out["slate_builder_missing_fields"] = ""
    out["slate_builder_price_available"] = True
    return out.to_dict("records")


def send_forward(rows: list[dict[str, Any]]) -> None:
    for key in ["fresh_odds_slate_builder_rows", "pro_predictor_latest_rows", "pro_predictor_high_confidence_rows", "odds_lock_pro_candidate_rows", "ara_latest_predictions", "public_proof_dashboard_refresh_rows"]:
        st.session_state[key] = rows
    try:
        workspace = str(st.session_state.get("aba_test_window_id") or "test_01")
        for key in ["fresh_odds_slate_builder_rows", "pro_predictor_latest_rows", "pro_predictor_high_confidence_rows", "odds_lock_pro_candidate_rows", "ara_latest_predictions"]:
            save_held_rows(key, rows, workspace)
            save_held_rows(key, rows, "test_01")
    except Exception:
        pass


st.title(t("title"))
st.caption(t("caption"))
st.info(t("quick_start"))
rows: list[dict[str, Any]] = []

st.subheader(t("fetch"))
selected_sport = st.selectbox(t("sport_preset"), list(SPORT_PRESETS.keys()), index=0, key="fosb_sport_preset")
selected_markets = st.multiselect(t("bet_types"), list(MARKET_LABELS.keys()), default=list(MARKET_LABELS.keys()), key="fosb_market_labels")
defaults = SPORT_PRESETS.get(selected_sport, SPORT_PRESETS["NBA"])
st.session_state.setdefault("fosb_custom_sport_key", defaults["sport_key"])
st.session_state.setdefault("fosb_regions", defaults["regions"])
st.session_state["fosb_markets"] = _selected_markets(selected_markets)

with st.expander(t("advanced_fetch"), expanded=False):
    st.text_input(t("sport_key"), value=defaults["sport_key"], key="fosb_custom_sport_key")
    st.text_input(t("regions"), value=defaults["regions"], key="fosb_regions")
    st.text_input(t("markets"), value=_selected_markets(selected_markets), key="fosb_markets")
    st.text_input(t("bookmakers"), value="", key="fosb_bookmakers")

if st.button(t("fetch_button"), type="primary"):
    sport_key, regions, markets, bookmakers = _current_fetch_settings()
    api_key = get_secret("ODDS_API_KEY", "THE_ODDS_API_KEY")
    if not api_key:
        st.warning(t("missing_key"))
    else:
        try:
            payload = fetch_the_odds_api_payload(api_key, sport_key=sport_key, regions=regions, markets=markets, bookmakers=bookmakers)
            rows = []
            for market in [item.strip() for item in markets.split(",") if item.strip()]:
                rows.extend(normalize_the_odds_api_events(payload, sport=sport_key, market=market, bookmaker_filter=bookmakers))
            st.session_state["fresh_odds_slate_builder_rows"] = rows
            st.success(f"Fetched rows: {len(rows)}") if rows else st.warning("API returned no usable rows for the selected settings.")
        except Exception as exc:
            st.error(f"Fresh odds fetch failed: {type(exc).__name__}: {str(exc)[:220]}")

with st.expander(t("csv_import"), expanded=True):
    csv_upload = st.file_uploader(t("csv_upload"), type=["csv"], key="fosb_predictor_csv_upload")
    if csv_upload is not None:
        try:
            rows = _ready_csv_rows(pd.read_csv(csv_upload))
            send_forward(rows)
            st.success(f"{t('csv_loaded')} Rows: {len(rows)}")
        except Exception as exc:
            st.error(f"CSV import failed: {type(exc).__name__}: {str(exc)[:220]}")

with st.expander(t("manual"), expanded=False):
    st.caption("Use this only when another tool already gave you a raw API response file.")
    api_name = st.selectbox(t("api_name"), ["The Odds API", "SportsDataIO"], index=0)
    upload = st.file_uploader(t("upload"), type=["json"])
    if upload is not None:
        try:
            rows = build_slate_rows_from_payload(api_name, _load_json_upload(upload), sport="", market="")
            st.session_state["fresh_odds_slate_builder_rows"] = rows
        except Exception as exc:
            st.error(f"JSON upload failed: {type(exc).__name__}: {str(exc)[:220]}")

rows = rows or st.session_state.get("fresh_odds_slate_builder_rows", []) or []
frame = pd.DataFrame(rows)
summary = slate_builder_summary(rows)
show_table(t("summary"), summary)
show_table(t("rows"), frame)
ready_frame = frame[frame.get("slate_builder_ready_for_advisory_pipeline", pd.Series(dtype=bool)).fillna(False).astype(bool)].copy() if not frame.empty else pd.DataFrame()
missing_frame = frame[frame.get("slate_builder_missing_fields", pd.Series(dtype=str)).fillna("").astype(str) != ""].copy() if not frame.empty else pd.DataFrame()
show_table(t("ready"), ready_frame)
show_table(t("missing"), missing_frame)

if not ready_frame.empty:
    if st.button(t("send"), type="primary"):
        send_forward(ready_frame.to_dict("records"))
        st.success(t("sent"))
    csv_link(t("download"), frame, "fresh_odds_slate_builder.csv")

with st.expander(t("report"), expanded=False):
    st.text_area(t("report"), value=slate_builder_report_section(rows), height=260)
