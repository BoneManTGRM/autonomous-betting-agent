import os

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.scorelines import estimate_scorelines, expected_goals_from_probability

st.set_page_config(page_title="Live Market Scanner", layout="wide")

language = st.selectbox("Language / Idioma", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "Live market scanner", "Español": "Escáner de mercado en vivo"},
    "caption": {
        "English": "Scan one provider feed safely. If a feed or region is unavailable, the app shows a warning instead of crashing.",
        "Español": "Revisa una fuente del proveedor de forma segura. Si una fuente o región no está disponible, la app muestra una advertencia en vez de fallar.",
    },
    "token": {"English": "Provider access token", "Español": "Clave de acceso del proveedor"},
    "token_help": {
        "English": "Paste your own provider access token above. It is used only for this browser session unless the app owner configures one separately.",
        "Español": "Pega tu propia clave de acceso arriba. Se usa solo en esta sesión del navegador, salvo que el dueño configure una clave aparte.",
    },
    "regions": {"English": "Bookmaker market regions", "Español": "Regiones de mercado de casas de apuestas"},
    "regions_help": {
        "English": "The Odds API regions: us, us2, uk, eu, au. These are bookmaker markets, not event host countries.",
        "Español": "Regiones de The Odds API: us, us2, uk, eu, au. Son mercados de casas de apuestas, no países sede del evento.",
    },
    "sport_search": {"English": "Sport search", "Español": "Buscar deporte"},
    "max_events": {"English": "Max events", "Español": "Máximo de eventos"},
    "choose_region": {"English": "Choose at least one market region.", "Español": "Elige al menos una región de mercado."},
    "sport_feed": {"English": "Sport feed", "Español": "Fuente deportiva"},
    "scan": {"English": "Scan", "Español": "Escanear"},
    "no_games": {"English": "No games with usable market data were returned for this feed.", "Español": "No se devolvieron partidos con datos de mercado utilizables para esta fuente."},
    "start": {"English": "Start", "Español": "Inicio"},
    "most_likely": {"English": "Most likely", "Español": "Más probable"},
    "outcome": {"English": "Outcome", "Español": "Resultado"},
    "price": {"English": "Price", "Español": "Precio"},
    "probability": {"English": "Probability", "Español": "Probabilidad"},
    "books": {"English": "Books", "Español": "Casas"},
    "scorelines": {"English": "Most likely scorelines / spread", "Español": "Marcadores / diferencia más probables"},
    "score": {"English": "Score", "Español": "Marcador"},
    "read": {"English": "Read", "Español": "Lectura"},
    "estimated": {"English": "Estimated probability", "Español": "Probabilidad estimada"},
    "draw": {"English": "Draw", "Español": "Empate"},
    "by": {"English": "by", "Español": "por"},
    "scoreline_missing": {
        "English": "Scoreline estimates require a mapped home-team probability. This feed may use a two-outcome or non-team market.",
        "Español": "Las estimaciones de marcador requieren una probabilidad local mapeada. Esta fuente puede usar un mercado de dos resultados o no ser de equipos.",
    },
    "research_note": {
        "English": "Market-based scan only. Add injuries, lineups, weather and team ratings before trusting a pick.",
        "Español": "Escaneo basado solo en mercado. Agrega lesiones, alineaciones, clima y ratings antes de confiar en una selección.",
    },
}


def t(key: str) -> str:
    return TEXT[key][language]


st.title(t("title"))
st.caption(t("caption"))

ALL_REGIONS = ["us", "us2", "uk", "eu", "au"]


def safe_error(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "Provider key was rejected. Check the key and plan access." if not IS_ES else "La clave del proveedor fue rechazada. Revisa la clave y el acceso del plan."
    if status == 422:
        return "This sport feed is not available for the selected market regions. Try fewer regions or another feed." if not IS_ES else "Esta fuente deportiva no está disponible para las regiones seleccionadas. Prueba menos regiones u otra fuente."
    if status == 429:
        return "Provider quota or rate limit reached. Wait or use another key." if not IS_ES else "Se alcanzó la cuota o límite del proveedor. Espera o usa otra clave."
    return "Provider request failed. Try another feed or region." if not IS_ES else "Falló la solicitud al proveedor. Prueba otra fuente o región."


def event_table(item):
    rows = []
    home_probability = None
    for outcome in item.outcomes:
        rows.append({
            t("outcome"): outcome.name,
            t("price"): round(outcome.average_price, 3),
            t("probability"): f"{outcome.normalized_probability:.1%}",
            t("books"): outcome.source_count,
        })
        if outcome.name == item.home_team:
            home_probability = outcome.normalized_probability
    return rows, home_probability


try:
    saved_token = str(st.secrets.get("THE_ODDS_API_KEY", ""))
except Exception:
    saved_token = os.getenv("THE_ODDS_API_KEY", "")

entry_token = st.text_input(t("token"), value="", type="password")
key = entry_token.strip() or saved_token

if not key:
    st.info(t("token_help"))
    st.stop()

selected_regions = st.multiselect(t("regions"), ALL_REGIONS, default=ALL_REGIONS, help=t("regions_help"))
st.caption(t("regions_help"))
search_text = st.text_input(t("sport_search"), "auto")
max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=15, step=1)

if not selected_regions:
    st.error(t("choose_region"))
    st.stop()

try:
    sports = list_sports(key, include_all=False)
except Exception as exc:
    st.error(safe_error(exc))
    st.stop()

terms = [x.lower() for x in search_text.split() if x.strip() and x.lower() != "auto"]
choices = []
for item in sports:
    text = f"{item.key} {item.group} {item.title} {item.description}".lower()
    if not terms or any(term in text for term in terms):
        choices.append(item)
if not choices:
    choices = sports

labels = [f"{item.title} | {item.key}" for item in choices]
selected = st.selectbox(t("sport_feed"), labels)
sport_key = choices[labels.index(selected)].key
region_text = ",".join(selected_regions)

if st.button(t("scan"), type="primary"):
    try:
        results = scan_market(key, sport_key, regions=region_text, max_events=int(max_events))
    except Exception as exc:
        st.warning(safe_error(exc))
        st.stop()

    if not results:
        st.info(t("no_games"))
        st.stop()

    for item in results:
        st.subheader(f"{item.away_team} at {item.home_team}")
        st.write(f"{t('start')}: {item.commence_time}")
        st.success(f"{t('most_likely')}: {item.favorite} ({item.favorite_probability:.1%})")
        rows, home_probability = event_table(item)
        st.dataframe(rows, use_container_width=True, hide_index=True)

        if home_probability is not None:
            home_xg, away_xg = expected_goals_from_probability(home_probability, neutral_site=False)
            score_rows = []
            for pick in estimate_scorelines(home_xg, away_xg):
                if pick.margin > 0:
                    margin = f"{item.home_team} {t('by')} {pick.margin}"
                elif pick.margin < 0:
                    margin = f"{item.away_team} {t('by')} {abs(pick.margin)}"
                else:
                    margin = t("draw")
                score_rows.append({t("score"): pick.label, t("read"): margin, t("estimated"): f"{pick.probability:.1%}"})
            st.write(t("scorelines"))
            st.dataframe(score_rows, use_container_width=True, hide_index=True)
        else:
            st.caption(t("scoreline_missing"))

        st.caption(t("research_note"))
