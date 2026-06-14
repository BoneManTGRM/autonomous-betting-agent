import os
from datetime import datetime, timezone

import streamlit as st

from autonomous_betting_agent.weather_context import fetch_weather, summary_to_dict


st.set_page_config(page_title="Weather Intelligence", layout="wide")

language = st.selectbox("Translate page", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "Weather Intelligence", "Español": "Inteligencia de Clima"},
    "caption": {
        "English": "Uses WeatherAPI.com to add outdoor-condition context for betting research. Weather is most useful for MLB, NFL, soccer, outdoor tennis, totals, and wind-sensitive games.",
        "Español": "Usa WeatherAPI.com para agregar contexto climático a la investigación. El clima ayuda más en MLB, NFL, fútbol, tenis al aire libre, totales y partidos sensibles al viento.",
    },
    "key": {"English": "WeatherAPI key", "Español": "Clave de WeatherAPI"},
    "location": {"English": "Location / stadium city", "Español": "Ubicación / ciudad del estadio"},
    "kickoff": {"English": "Game time ISO, optional", "Español": "Hora del juego ISO, opcional"},
    "run": {"English": "Check weather", "Español": "Revisar clima"},
    "risk": {"English": "Weather risk", "Español": "Riesgo climático"},
    "notes": {"English": "Weather notes", "Español": "Notas de clima"},
    "help": {
        "English": "Set WEATHERAPI_KEY in Streamlit secrets to avoid typing the key. Example game time: 2026-06-14T19:05:00Z. Leave blank for current weather.",
        "Español": "Guarda WEATHERAPI_KEY en los secretos de Streamlit para no escribir la clave. Ejemplo de hora: 2026-06-14T19:05:00Z. Déjalo vacío para clima actual.",
    },
}


def t(key: str) -> str:
    return TEXT.get(key, {}).get(language) or TEXT.get(key, {}).get("English") or key


st.title(t("title"))
st.caption(t("caption"))
st.info(t("help"))

try:
    saved_weather_key = str(st.secrets.get("WEATHERAPI_KEY", ""))
except Exception:
    saved_weather_key = os.getenv("WEATHERAPI_KEY", "")

weather_key = st.text_input(t("key"), type="password").strip() or saved_weather_key
location = st.text_input(t("location"), "New York")
kickoff = st.text_input(t("kickoff"), "")

if not weather_key:
    st.info("Paste your WeatherAPI key or add WEATHERAPI_KEY to Streamlit secrets." if not IS_ES else "Pega tu clave de WeatherAPI o agrega WEATHERAPI_KEY a los secretos de Streamlit.")
    st.stop()

if st.button(t("run"), type="primary"):
    try:
        summary = fetch_weather(weather_key, location, kickoff or None)
    except Exception as exc:
        st.error(f"WeatherAPI request failed: {exc}" if not IS_ES else f"Falló la solicitud de WeatherAPI: {exc}")
        st.stop()

    st.subheader(summary.location)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Condition" if not IS_ES else "Condición", summary.condition)
    c2.metric("Temp" if not IS_ES else "Temp", "" if summary.temp_f is None else f"{summary.temp_f:.0f}F")
    c3.metric("Wind" if not IS_ES else "Viento", "" if summary.wind_mph is None else f"{summary.wind_mph:.0f} mph {summary.wind_dir}")
    c4.metric(t("risk"), f"{summary.weather_risk}/50")

    if summary.weather_risk >= 25:
        st.warning(f"{t('notes')}: " + "; ".join(summary.weather_notes))
    elif summary.weather_risk >= 12:
        st.info(f"{t('notes')}: " + "; ".join(summary.weather_notes))
    else:
        st.success(f"{t('notes')}: " + "; ".join(summary.weather_notes))

    st.dataframe([summary_to_dict(summary)], use_container_width=True, hide_index=True)
    st.caption(f"Fetched at {datetime.now(timezone.utc).isoformat()}")
