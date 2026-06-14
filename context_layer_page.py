from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import streamlit as st

from autonomous_betting_agent.ui_text import LANGUAGES, tr


@dataclass(frozen=True)
class ContextLayerConfig:
    language: str
    odds_enabled: bool
    weather_enabled: bool
    sports_enabled: bool
    game: str
    sport_search: str
    weather_location: str
    book_regions: list[str]
    markets: list[str]
    temp_f: float
    wind_mph: float
    rain_mm: float


st.set_page_config(page_title="Decision Layer", page_icon="🌦️", layout="wide")

language_name = st.selectbox("Language / Idioma", list(LANGUAGES.keys()), index=0)
lang = LANGUAGES[language_name]

st.title(tr("odds_weather_title", lang))
st.caption(tr("odds_weather_caption", lang))

st.subheader(tr("api_sources", lang))
api1, api2, api3 = st.columns(3)
with api1:
    odds_key = st.text_input(tr("odds_api_key", lang), type="password")
with api2:
    weather_key = st.text_input(tr("weatherapi_key", lang), type="password")
with api3:
    sports_key = st.text_input(tr("sportsdataio_key", lang), type="password")

st.subheader(tr("game_setup", lang))
c1, c2 = st.columns(2)
with c1:
    game = st.text_input(tr("game", lang), value="Mexico vs South Korea")
    sport_search = st.text_input(tr("sport_search", lang), value="soccer")
with c2:
    weather_location = st.text_input(tr("weather_location", lang), value="")
    book_regions = st.multiselect(tr("book_regions", lang), ["us", "us2", "uk", "eu", "au"], default=["us", "us2", "uk", "eu"])

markets = st.multiselect(tr("markets", lang), ["h2h", "spreads", "totals"], default=["h2h", "spreads", "totals"])

st.subheader(tr("manual_weather", lang))
w1, w2, w3 = st.columns(3)
temp_f = w1.number_input(tr("temperature", lang), min_value=-40.0, max_value=130.0, value=70.0)
wind_mph = w2.number_input(tr("wind", lang), min_value=0.0, max_value=100.0, value=0.0)
rain_mm = w3.number_input(tr("rain", lang), min_value=0.0, max_value=200.0, value=0.0)

st.subheader(tr("source_status", lang))
s1, s2, s3 = st.columns(3)
s1.metric("Odds", tr("enabled", lang) if odds_key.strip() else tr("missing", lang))
s2.metric("Weather", tr("enabled", lang) if weather_key.strip() else tr("missing", lang))
s3.metric("Sports", tr("enabled", lang) if sports_key.strip() else tr("missing", lang))

config = ContextLayerConfig(
    language=lang,
    odds_enabled=bool(odds_key.strip()),
    weather_enabled=bool(weather_key.strip()),
    sports_enabled=bool(sports_key.strip()),
    game=game,
    sport_search=sport_search,
    weather_location=weather_location,
    book_regions=book_regions,
    markets=markets,
    temp_f=float(temp_f),
    wind_mph=float(wind_mph),
    rain_mm=float(rain_mm),
)

if st.button(tr("run_layer", lang), type="primary", use_container_width=True):
    score = 100.0
    if wind_mph >= 20:
        score -= 30.0
    elif wind_mph >= 12:
        score -= 12.0
    if rain_mm >= 5:
        score -= 20.0
    elif rain_mm > 0:
        score -= 8.0
    score = max(0.0, min(100.0, score))
    st.subheader(tr("decision_output", lang))
    o1, o2, o3 = st.columns(3)
    o1.metric(tr("weather_score", lang), f"{score:.1f}/100")
    o2.metric(tr("markets_selected", lang), len(markets))
    o3.metric("Sources", sum([config.odds_enabled, config.weather_enabled, config.sports_enabled]))
    st.subheader(tr("config", lang))
    st.code(json.dumps(asdict(config), indent=2), language="json")
else:
    st.info(tr("enter_fields", lang))
