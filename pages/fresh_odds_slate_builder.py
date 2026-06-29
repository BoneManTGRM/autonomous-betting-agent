from __future__ import annotations

import base64
import html
import json
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
from autonomous_betting_agent.sidebar_nav import render_app_sidebar
from autonomous_betting_agent.ui_i18n import localize_dataframe

st.set_page_config(page_title="Fresh Odds Slate Builder", layout="wide")
LANG = render_app_sidebar("fresh_odds_slate_builder", language_key="fresh_odds_slate_builder_language", selector="radio")

TEXT = {
    "en": {
        "title": "Fresh Odds Slate Builder",
        "caption": "Phase 3E.6.3 Streamlit/session-only future-event slate builder.",
        "safety": "Safety",
        "fetch": "Fetch from The Odds API",
        "manual": "Upload API JSON payload",
        "sport_key": "The Odds API sport key",
        "regions": "Regions",
        "markets": "Markets",
        "bookmakers": "Bookmakers filter, optional",
        "fetch_button": "Fetch fresh odds slate now",
        "missing_key": "ODDS_API_KEY is not configured in Streamlit secrets. Enter it in secrets before fetching.",
        "upload": "Upload JSON from an API response",
        "api_name": "API payload type",
        "summary": "Slate Builder Summary",
        "rows": "Generated Slate Rows",
        "ready": "Rows ready for advisory pipeline",
        "missing": "Rows missing fields",
        "report": "Copy/paste slate report",
        "send": "Send ready rows to advisory session rows",
        "sent": "Ready rows were copied into session rows for advisory review.",
        "download": "Download slate CSV",
    },
    "es": {
        "title": "Constructor de Slate de Odds Frescas",
        "caption": "Fase 3E.6.3 constructor de slate futuro solo Streamlit/sesion.",
        "safety": "Seguridad",
        "fetch": "Consultar The Odds API",
        "manual": "Subir payload JSON de API",
        "sport_key": "Clave deporte The Odds API",
        "regions": "Regiones",
        "markets": "Mercados",
        "bookmakers": "Filtro bookmakers, opcional",
        "fetch_button": "Consultar slate de odds frescas ahora",
        "missing_key": "ODDS_API_KEY no esta configurada en Streamlit secrets. Agregala antes de consultar.",
        "upload": "Subir JSON de una respuesta API",
        "api_name": "Tipo de payload API",
        "summary": "Resumen del constructor de slate",
        "rows": "Filas generadas",
        "ready": "Filas listas para asesoría",
        "missing": "Filas con campos faltantes",
        "report": "Reporte de slate para copiar/pegar",
        "send": "Enviar filas listas a sesion asesoría",
        "sent": "Las filas listas fueron copiadas a la sesion para revisión asesoría.",
        "download": "Descargar CSV de slate",
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT["en"]).get(key, TEXT["en"].get(key, key))


def display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return localize_dataframe(frame, LANG)


def csv_link(label: str, frame: pd.DataFrame, filename: str) -> None:
    data = base64.b64encode(frame.to_csv(index=False).encode("utf-8")).decode("ascii")
    st.markdown(
        f'<a href="data:text/csv;base64,{data}" download="{html.escape(filename)}" '
        f'style="display:block;text-align:center;background:#ef5350;color:white;'
        f'padding:.75rem 1rem;border-radius:.45rem;text-decoration:none;font-weight:700;">'
        f'{html.escape(label)}</a>',
        unsafe_allow_html=True,
    )


def show_table(title: str, frame: pd.DataFrame) -> None:
    st.subheader(title)
    if frame.empty:
        st.info("No rows.")
    else:
        st.dataframe(display_frame(frame), use_container_width=True, hide_index=True)


def _load_json_upload(upload: Any) -> Any:
    if upload is None:
        return None
    content = upload.read().decode("utf-8")
    return json.loads(content)


st.title(t("title"))
st.caption(t("caption"))

st.subheader(t("safety"))
st.warning(
    "Fresh Odds Slate Builder is Streamlit/session-only. It uses user-triggered API calls only. "
    "It does not expose API keys, create a server, database, scheduler, background worker, persistent cache, "
    "subscriber API layer, proof mutation, result mutation, live betting, or bankroll/staking action."
)
st.json({
    "phase": "3E.6.3",
    "streamlit_session_only": True,
    "user_triggered_only": True,
    "api_key_exposed": False,
    "server_added": False,
    "database_added": False,
    "scheduled_polling": False,
    "live_betting": False,
    "proof_mutation": False,
})

rows: list[dict[str, Any]] = []

with st.expander(t("fetch"), expanded=True):
    sport_key = st.text_input(t("sport_key"), value="basketball_nba")
    regions = st.text_input(t("regions"), value="us")
    markets = st.text_input(t("markets"), value="h2h")
    bookmakers = st.text_input(t("bookmakers"), value="")
    if st.button(t("fetch_button")):
        api_key = str(st.secrets.get("ODDS_API_KEY", "") or "")
        if not api_key:
            st.warning(t("missing_key"))
        else:
            try:
                payload = fetch_the_odds_api_payload(
                    api_key,
                    sport_key=sport_key,
                    regions=regions,
                    markets=markets,
                    bookmakers=bookmakers,
                )
                rows = normalize_the_odds_api_events(payload, sport=sport_key, market=markets.split(",")[0].strip(), bookmaker_filter=bookmakers.strip())
                st.session_state["fresh_odds_slate_builder_rows"] = rows
            except Exception as exc:
                st.error(f"Fresh odds fetch failed: {type(exc).__name__}")

with st.expander(t("manual"), expanded=False):
    api_name = st.selectbox(t("api_name"), ["The Odds API", "SportsDataIO"], index=0)
    upload = st.file_uploader(t("upload"), type=["json"])
    if upload is not None:
        try:
            payload = _load_json_upload(upload)
            rows = build_slate_rows_from_payload(api_name, payload, sport="", market="")
            st.session_state["fresh_odds_slate_builder_rows"] = rows
        except Exception as exc:
            st.error(f"JSON upload failed: {type(exc).__name__}")

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
    if st.button(t("send")):
        ready_rows = ready_frame.to_dict("records")
        st.session_state["fresh_odds_slate_builder_rows"] = ready_rows
        st.session_state["pro_predictor_latest_rows"] = ready_rows
        st.success(t("sent"))
    csv_link(t("download"), frame, "fresh_odds_slate_builder.csv")

st.subheader(t("report"))
st.text_area(t("report"), value=slate_builder_report_section(rows), height=260)
