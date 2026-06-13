import os
import unicodedata
from difflib import SequenceMatcher

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.scorelines import estimate_scorelines, expected_goals_from_probability

st.set_page_config(page_title="Autonomous Betting Agent", layout="wide")

language = st.selectbox("Language / Idioma", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "Autonomous Betting Agent", "Español": "Agente Autónomo de Pronósticos"},
    "caption": {
        "English": "Paste a provider token, enter two teams, and let the agent search feeds, rank likely outcomes, and estimate scorelines.",
        "Español": "Pega una clave del proveedor, escribe dos equipos y deja que el agente busque partidos, ordene resultados probables y estime marcadores.",
    },
    "token": {"English": "Provider access token", "Español": "Clave de acceso del proveedor"},
    "token_help": {
        "English": "Paste your own provider access token above. It is used only for this browser session unless the app owner configures one separately.",
        "Español": "Pega tu propia clave de acceso arriba. Se usa solo en esta sesión del navegador, salvo que el dueño configure una clave aparte.",
    },
    "team1": {"English": "Team 1", "Español": "Equipo 1"},
    "team2": {"English": "Team 2", "Español": "Equipo 2"},
    "competition": {"English": "Sport / competition", "Español": "Deporte / competición"},
    "advanced": {"English": "Advanced settings", "Español": "Configuración avanzada"},
    "market_regions": {"English": "Bookmaker market regions", "Español": "Regiones de mercado de casas de apuestas"},
    "host_note": {
        "English": "FIFA 2026 host countries are Canada, Mexico and the USA. The region selector below is for bookmaker markets, not host countries.",
        "Español": "Las sedes de FIFA 2026 son Canadá, México y Estados Unidos. El selector de regiones abajo es para mercados de casas de apuestas, no para países sede.",
    },
    "max_feeds": {"English": "Max feeds to scan", "Español": "Máximo de fuentes a revisar"},
    "max_events": {"English": "Max games per feed", "Español": "Máximo de partidos por fuente"},
    "nearest": {"English": "Show closest games if no exact match", "Español": "Mostrar partidos más cercanos si no hay coincidencia exacta"},
    "run": {"English": "Run autonomous agent", "Español": "Ejecutar agente autónomo"},
    "loading": {"English": "Loading and ranking sport feeds", "Español": "Cargando y clasificando fuentes deportivas"},
    "searching": {"English": "Searching games and building report", "Español": "Buscando partidos y construyendo reporte"},
    "choose_region": {"English": "Choose at least one market region.", "Español": "Elige al menos una región de mercado."},
    "could_not_load": {"English": "Could not load sport feeds", "Español": "No se pudieron cargar las fuentes deportivas"},
    "scanned": {"English": "Scanned", "Español": "Revisó"},
    "feeds_found": {"English": "feeds and found", "Español": "fuentes y encontró"},
    "games_market": {"English": "games with market data.", "Español": "partidos con datos de mercado."},
    "skipped": {"English": "Skipped", "Español": "Omitidas"},
    "no_match": {
        "English": "No exact team match found. The provider may not have this game yet, or the team names may be listed differently.",
        "Español": "No se encontró una coincidencia exacta. Puede que el proveedor todavía no tenga este partido o que los equipos aparezcan con otros nombres.",
    },
    "closest": {"English": "Closest games found", "Español": "Partidos más cercanos encontrados"},
    "try_terms": {
        "English": "Try competition terms like international soccer, fifa, world cup, concacaf, nba, nfl, mlb, tennis, or choose more market regions.",
        "Español": "Prueba términos como international soccer, fifa, world cup, concacaf, nba, nfl, mlb, tennis, o elige más regiones de mercado.",
    },
    "team_confidence": {"English": "Team-match confidence", "Español": "Confianza de coincidencia"},
    "start": {"English": "Start", "Español": "Inicio"},
    "likely": {"English": "Most likely outcome", "Español": "Resultado más probable"},
    "outcome": {"English": "Outcome", "Español": "Resultado"},
    "avg_price": {"English": "Avg market price", "Español": "Precio promedio"},
    "probability": {"English": "No-vig probability", "Español": "Probabilidad sin margen"},
    "sources": {"English": "Sources", "Español": "Fuentes"},
    "scorelines": {"English": "Most likely scorelines / spread", "Español": "Marcadores / diferencia más probables"},
    "score": {"English": "Score", "Español": "Marcador"},
    "spread": {"English": "Spread", "Español": "Diferencia"},
    "draw": {"English": "Draw", "Español": "Empate"},
    "by": {"English": "by", "Español": "por"},
    "cycle": {"English": "ARA cycle notes", "Español": "Notas del ciclo ARA"},
    "research_note": {
        "English": "Research estimate only. This uses market data until team-stat, injury, lineup, and weather providers are added.",
        "Español": "Estimación de investigación solamente. Usa datos de mercado hasta que se agreguen estadísticas, lesiones, alineaciones y clima.",
    },
}


def t(key: str) -> str:
    return TEXT[key][language]


st.title(t("title"))
st.caption(t("caption"))

COUNTRY_ALIASES = {
    "mexico": ["mexico", "méxico", "mexican", "el tri"],
    "south korea": ["south korea", "korea republic", "republic of korea", "korea"],
    "usa": ["usa", "united states", "usmnt", "united states of america"],
    "united states": ["usa", "united states", "usmnt", "united states of america"],
    "canada": ["canada", "canadá", "canadian"],
    "england": ["england", "english"],
    "brazil": ["brazil", "brasil"],
    "germany": ["germany", "deutschland"],
    "spain": ["spain", "españa"],
    "argentina": ["argentina"],
    "france": ["france"],
    "japan": ["japan"],
}


def read_provider_token() -> str:
    try:
        return str(st.secrets.get("THE_ODDS_API_KEY", ""))
    except Exception:
        return os.getenv("THE_ODDS_API_KEY", "")


def clean(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().replace("-", " ").replace(".", " ").split())


def aliases(value: str) -> list[str]:
    base = clean(value)
    values = {base}
    for key, alias_list in COUNTRY_ALIASES.items():
        if base == clean(key) or base in [clean(alias) for alias in alias_list]:
            values.update(clean(alias) for alias in alias_list)
    return [item for item in values if item]


def is_known_country(value: str) -> bool:
    base = clean(value)
    for key, alias_list in COUNTRY_ALIASES.items():
        if base == clean(key) or base in [clean(alias) for alias in alias_list]:
            return True
    return False


def match_score(query: str, candidate: str) -> float:
    query = clean(query)
    candidate = clean(candidate)
    if not query or not candidate:
        return 0.0
    if query in candidate or candidate in query:
        return 1.0
    return SequenceMatcher(None, query, candidate).ratio()


def best_name_score(query: str, names: list[str]) -> float:
    if not query:
        return 1.0
    return max(match_score(alias, name) for alias in aliases(query) for name in names)


def event_score(item, team_one: str, team_two: str) -> float:
    names = [item.home_team, item.away_team] + [outcome.name for outcome in item.outcomes]
    one_score = best_name_score(team_one, names)
    two_score = best_name_score(team_two, names)
    if team_one and team_two:
        return (one_score + two_score) / 2.0
    return max(one_score, two_score)


def sport_score(sport_item, competition: str, team_one: str, team_two: str) -> float:
    haystack = clean(f"{sport_item.key} {sport_item.group} {sport_item.title} {sport_item.description}")
    words = [clean(word) for word in competition.split() if clean(word)]
    score_value = 0.0
    for word in words:
        if word in haystack:
            score_value += 4.0
    national_matchup = is_known_country(team_one) and is_known_country(team_two)
    if national_matchup:
        for word in ["international", "world", "fifa", "cup", "friendlies", "concacaf", "uefa"]:
            if word in haystack:
                score_value += 6.0
        for domestic_word in ["serie", "division", "league", "liga", "campeonato", "superleague"]:
            if domestic_word in haystack and "international" not in haystack and "world" not in haystack:
                score_value -= 3.0
    return score_value


def explain_error(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "provider token was rejected" if not IS_ES else "la clave del proveedor fue rechazada"
    if status == 422:
        return "feed is not available for the selected market regions" if not IS_ES else "la fuente no está disponible para las regiones de mercado seleccionadas"
    if status == 429:
        return "provider quota or rate limit reached" if not IS_ES else "se alcanzó la cuota o límite del proveedor"
    return "provider request failed" if not IS_ES else "falló la solicitud al proveedor"


def show_event(item, score_value: float | None = None) -> None:
    st.subheader(f"{item.away_team} at {item.home_team}")
    if score_value is not None:
        st.write(f"{t('team_confidence')}: {score_value:.0%}")
    st.write(f"{t('start')}: {item.commence_time}")
    st.write(f"{t('likely')}: {item.favorite} ({item.favorite_probability:.1%})")

    rows = []
    home_probability = None
    for outcome in item.outcomes:
        rows.append({t("outcome"): outcome.name, t("avg_price"): round(outcome.average_price, 3), t("probability"): f"{outcome.normalized_probability:.1%}", t("sources"): outcome.source_count})
        if clean(outcome.name) == clean(item.home_team):
            home_probability = outcome.normalized_probability
    st.dataframe(rows, use_container_width=True, hide_index=True)

    if home_probability is not None:
        home_xg, away_xg = expected_goals_from_probability(home_probability, neutral_site=False)
        score_rows = []
        for pick in estimate_scorelines(home_xg, away_xg):
            if pick.margin > 0:
                spread = f"{item.home_team} {t('by')} {pick.margin}"
            elif pick.margin < 0:
                spread = f"{item.away_team} {t('by')} {abs(pick.margin)}"
            else:
                spread = t("draw")
            score_rows.append({t("score"): pick.label, t("spread"): spread, t("probability"): f"{pick.probability:.1%}"})
        st.write(t("scorelines"))
        st.dataframe(score_rows, use_container_width=True, hide_index=True)

    with st.expander(t("cycle")):
        for note in item.cycle_notes:
            st.write(f"- {note}")
    st.caption(t("research_note"))


saved_token = read_provider_token()
entry_token = st.text_input(t("token"), value="", type="password")
provider_token = entry_token.strip() or saved_token
if not provider_token:
    st.info(t("token_help"))
    st.stop()

team_one = st.text_input(t("team1"), "")
team_two = st.text_input(t("team2"), "")
competition = st.text_input(t("competition"), "international soccer")

with st.expander(t("advanced")):
    st.caption(t("host_note"))
    selected_regions = st.multiselect(t("market_regions"), ["us", "uk", "eu", "au"], default=["us", "eu", "uk"])
    max_feeds = st.number_input(t("max_feeds"), min_value=1, max_value=30, value=12, step=1)
    max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=30, step=1)
    show_nearest = st.checkbox(t("nearest"), value=True)

if st.button(t("run"), type="primary"):
    if not selected_regions:
        st.error(t("choose_region"))
        st.stop()

    with st.spinner(t("loading")):
        try:
            sports = list_sports(provider_token, include_all=False)
        except Exception as exc:
            st.error(f"{t('could_not_load')}: {explain_error(exc)}")
            st.stop()

    ranked_sports = sorted(
        sports,
        key=lambda item: sport_score(item, competition, team_one, team_two),
        reverse=True,
    )
    candidate_sports = ranked_sports[: int(max_feeds)]
    region_text = ",".join(selected_regions)
    all_results = []
    skipped = []

    with st.spinner(t("searching")):
        for sport_item in candidate_sports:
            try:
                all_results.extend(scan_market(provider_token, sport_key=sport_item.key, regions=region_text, max_events=int(max_events)))
            except Exception as exc:
                skipped.append((sport_item.title, explain_error(exc)))

    scored = sorted(
        [(event_score(item, team_one, team_two), item) for item in all_results],
        key=lambda pair: pair[0],
        reverse=True,
    )
    matches = [(score_value, item) for score_value, item in scored if score_value >= 0.55]

    st.write(f"{t('scanned')} {len(candidate_sports)} {t('feeds_found')} {len(all_results)} {t('games_market')}")
    if skipped:
        with st.expander(f"{t('skipped')} {len(skipped)}"):
            for title, reason in skipped[:20]:
                st.write(f"- {title}: {reason}")

    if matches:
        for score_value, item in matches[:10]:
            show_event(item, score_value)
    else:
        st.info(t("no_match"))
        if show_nearest and scored:
            st.write(t("closest"))
            for score_value, item in scored[:5]:
                show_event(item, score_value)
        else:
            st.write(t("try_terms"))
