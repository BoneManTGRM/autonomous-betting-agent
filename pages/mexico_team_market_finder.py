import os
import unicodedata
from difflib import SequenceMatcher
from types import SimpleNamespace

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.scorelines import estimate_scorelines, expected_goals_from_probability

st.set_page_config(page_title="Mexico Team Market Finder", layout="wide")

language = st.selectbox("Language / Idioma", ["English", "Español"], index=0)
IS_ES = language == "Español"

LABELS = {
    "title": {"English": "Mexico Team Market Finder", "Español": "Buscador de Equipos Mexicanos"},
    "caption": {
        "English": "Strict matcher for Mexico national team and Mexican clubs. It searches odds-provider markets only. If the provider has no current odds for the selected club, the page will say that clearly and will not treat unrelated teams as matches.",
        "Español": "Buscador estricto para Selección Mexicana y clubes mexicanos. Solo busca mercados del proveedor de odds. Si el proveedor no tiene odds actuales para el club seleccionado, la página lo dirá claramente y no tratará equipos sin relación como coincidencias.",
    },
    "token": {"English": "Provider key", "Español": "Clave del proveedor"},
    "team": {"English": "Team", "Español": "Equipo"},
    "custom": {"English": "Custom search", "Español": "Búsqueda manual"},
    "league": {"English": "League search", "Español": "Buscar liga"},
    "regions": {"English": "Regions", "Español": "Regiones"},
    "scan": {"English": "Search selected team", "Español": "Buscar equipo seleccionado"},
    "no_team": {"English": "No current odds market was found for the selected team. This is not a matcher error; it means the odds provider did not return that club/team in the scanned markets right now.", "Español": "No se encontró un mercado de odds actual para el equipo seleccionado. No es un error de coincidencia; significa que el proveedor no devolvió ese club/equipo en los mercados escaneados ahora mismo."},
    "general": {"English": "General soccer markets found", "Español": "Mercados generales de futbol encontrados"},
    "matches": {"English": "Selected team matches", "Español": "Coincidencias del equipo seleccionado"},
    "all": {"English": "All scanned markets", "Español": "Todos los mercados escaneados"},
    "diag": {"English": "Diagnostics", "Español": "Diagnóstico"},
    "start": {"English": "Start", "Español": "Inicio"},
    "lean": {"English": "Market lean", "Español": "Lectura de mercado"},
    "prob": {"English": "Probability", "Español": "Probabilidad"},
    "price": {"English": "Best price", "Español": "Mejor precio"},
    "quality": {"English": "Market data quality", "Español": "Calidad de datos"},
    "raw": {"English": "Raw market table", "Español": "Tabla cruda"},
    "scorelines": {"English": "Likely scorelines", "Español": "Marcadores probables"},
    "score": {"English": "Score", "Español": "Marcador"},
    "read": {"English": "Read", "Español": "Lectura"},
    "estimated": {"English": "Estimated probability", "Español": "Probabilidad estimada"},
    "draw": {"English": "Draw", "Español": "Empate"},
    "by": {"English": "by", "Español": "por"},
    "selected": {"English": "Selected team", "Español": "Equipo seleccionado"},
    "events": {"English": "Markets returned", "Español": "Mercados devueltos"},
    "found": {"English": "Team markets found", "Español": "Mercados del equipo"},
    "skipped": {"English": "Skipped feeds", "Español": "Fuentes omitidas"},
}

TEAMS = {
    "Mexico national team": ["mexico", "méxico", "mex", "el tri", "seleccion mexicana", "selección mexicana"],
    "Chivas / Guadalajara": ["chivas", "guadalajara", "cd guadalajara", "club deportivo guadalajara", "deportivo guadalajara", "chivas guadalajara", "guadalajara chivas", "chivas de guadalajara", "cd chivas"],
    "Club America": ["america", "américa", "club america", "club américa", "aguilas", "águilas"],
    "Cruz Azul": ["cruz azul", "la maquina", "máquina"],
    "Pumas UNAM": ["pumas", "pumas unam", "unam"],
    "Tigres UANL": ["tigres", "tigres uanl", "uanl"],
    "Monterrey / Rayados": ["monterrey", "rayados", "cf monterrey"],
    "Toluca": ["toluca", "deportivo toluca"],
    "Pachuca": ["pachuca", "tuzos"],
    "Leon": ["leon", "león", "club leon", "club león"],
    "Santos Laguna": ["santos laguna", "santos"],
    "Atlas": ["atlas", "atlas fc"],
    "Tijuana / Xolos": ["tijuana", "xolos", "club tijuana"],
    "Puebla": ["puebla", "club puebla"],
    "Necaxa": ["necaxa"],
    "Queretaro": ["queretaro", "querétaro", "gallos blancos"],
    "Juarez / Bravos": ["juarez", "juárez", "fc juarez", "fc juárez", "bravos"],
    "Mazatlan": ["mazatlan", "mazatlán", "mazatlan fc", "mazatlán fc"],
    "Atletico San Luis": ["atletico san luis", "atlético san luis", "san luis"],
}

ALL_REGIONS = ["us", "eu", "uk", "us2", "au"]


def tr(key):
    return LABELS.get(key, {}).get(language) or LABELS.get(key, {}).get("English") or key


def clean(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().replace("-", " ").replace(".", " ").split())


def aliases_for(team, custom):
    if custom.strip():
        base = clean(custom)
        aliases = {base}
        for values in TEAMS.values():
            cleaned = [clean(v) for v in values]
            if base in cleaned:
                aliases.update(cleaned)
        return sorted(aliases)
    return sorted(clean(v) for v in TEAMS[team])


def alias_score(alias, name):
    alias = clean(alias)
    name = clean(name)
    if not alias or not name:
        return 0.0
    if len(alias) <= 3:
        return 1.0 if alias in set(name.split()) else 0.0
    if alias in name:
        return 1.0
    if len(name) >= 4 and name in alias:
        return 0.92
    ratio = SequenceMatcher(None, alias, name).ratio()
    return ratio if ratio >= 0.88 else 0.0


def team_match(event, aliases):
    names = [event.home_team, event.away_team] + [o.name for o in event.outcomes]
    best_score = 0.0
    best_text = ""
    for alias in aliases:
        for name in names:
            score = alias_score(alias, name)
            if score > best_score:
                best_score = score
                best_text = f"{alias} -> {name}"
    return best_score, best_text


def sport_score(sport, query):
    text = clean(f"{sport.key} {sport.group} {sport.title} {sport.description}")
    score = 0.0
    for word in ["soccer", "fifa", "world", "liga mx", "mexico", "mexican", "concacaf", "friendlies"]:
        if clean(word) in text:
            score += 10
    for word in [clean(w) for w in query.split() if clean(w)]:
        if word in text:
            score += 12
    if any(w in text for w in ["winner", "championship", "outright"]):
        score -= 25
    return score


def safe_error(exc):
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (401, 403):
        return "key rejected"
    if status == 422:
        return "region/feed unavailable"
    if status == 429:
        return "quota or rate limit"
    return "request failed"


def scan_feed(api_key, sport_key, regions, max_events):
    attempts = [",".join(regions)] + regions
    seen = set()
    found = []
    errors = []
    for region in attempts:
        try:
            events = scan_market(api_key, sport_key, regions=region, max_events=max_events)
            for event in events:
                key = event.event_id or f"{event.sport_key}:{event.home_team}:{event.away_team}:{event.commence_time}"
                if key not in seen:
                    seen.add(key)
                    found.append(event)
            if found:
                return found, errors
        except Exception as exc:
            errors.append(f"{region}: {safe_error(exc)}")
    return found, errors


def top_non_draw(event):
    return next((o for o in event.outcomes if clean(o.name) != "draw"), event.outcomes[0])


def snapshot(event, score, matched):
    top = top_non_draw(event)
    second = event.outcomes[1] if len(event.outcomes) > 1 else None
    gap = event.outcomes[0].normalized_probability - (second.normalized_probability if second else 0)
    quality = max(0, min(100, round(48 + min(event.bookmaker_count, 12) * 3 + min(gap, 0.30) * 70)))
    return {
        "Event": f"{event.away_team} at {event.home_team}",
        "Sport": event.sport_title,
        "Start": event.commence_time,
        "Market lean": top.name,
        "Probability": f"{top.normalized_probability:.1%}",
        "Match": f"{score:.0%}",
        "Matched": matched,
        "Best price": round((getattr(top, "best_price", None) or top.average_price), 3),
        "Books": event.bookmaker_count,
        "Market data quality": quality,
        "_event": event,
        "_score": score,
        "_prob": top.normalized_probability,
    }


def market_table(event):
    rows = []
    home_prob = None
    for o in event.outcomes:
        rows.append({
            "Outcome": o.name,
            "Average price": round(o.average_price, 3),
            "Best price": round((getattr(o, "best_price", None) or o.average_price), 3),
            "Best book": getattr(o, "best_bookmaker", None) or "",
            "Probability": f"{o.normalized_probability:.1%}",
            "Books": o.source_count,
        })
        if o.name == event.home_team:
            home_prob = o.normalized_probability
    return rows, home_prob


def scorelines(event):
    _, home_prob = market_table(event)
    if home_prob is None:
        return []
    home_xg, away_xg = expected_goals_from_probability(home_prob, neutral_site=False)
    rows = []
    for pick in estimate_scorelines(home_xg, away_xg):
        if pick.margin > 0:
            read = f"{event.home_team} {tr('by')} {pick.margin}"
        elif pick.margin < 0:
            read = f"{event.away_team} {tr('by')} {abs(pick.margin)}"
        else:
            read = tr("draw")
        rows.append({tr("score"): pick.label, tr("read"): read, tr("estimated"): f"{pick.probability:.1%}"})
    return rows


def show_event(row, expanded=False):
    event = row["_event"]
    with st.expander(f"{row['Event']} | {row['Market lean']} {row['Probability']} | Match {row['Match']}", expanded=expanded):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(tr("lean"), row["Market lean"])
        c2.metric(tr("prob"), row["Probability"])
        c3.metric(tr("price"), row["Best price"])
        c4.metric(tr("quality"), f"{row['Market data quality']}/100")
        st.write(f"{tr('start')}: {row['Start']}")
        st.write(f"Matched: {row['Matched']}")
        sc = scorelines(event)
        if sc:
            st.write(tr("scorelines"))
            st.dataframe(sc, use_container_width=True, hide_index=True)
        with st.expander(tr("raw")):
            mt, _ = market_table(event)
            st.dataframe(mt, use_container_width=True, hide_index=True)


st.title(tr("title"))
st.caption(tr("caption"))

try:
    saved_key = str(st.secrets.get("THE_ODDS_API_KEY", ""))
except Exception:
    saved_key = os.getenv("THE_ODDS_API_KEY", "")

api_key = st.text_input(tr("token"), type="password").strip() or saved_key
if not api_key:
    st.info("Paste a provider key." if not IS_ES else "Pega una clave del proveedor.")
    st.stop()

team = st.selectbox(tr("team"), list(TEAMS.keys()), index=1)
custom = st.text_input(tr("custom"), "")
query = st.text_input(tr("league"), "soccer mexico liga mx")
regions = st.multiselect(tr("regions"), ALL_REGIONS, default=["us", "eu", "uk"])
max_feeds = st.number_input("Max feeds", min_value=1, max_value=100, value=50)
max_events = st.number_input("Max events per feed", min_value=1, max_value=50, value=50)

selected_name = custom.strip() or team
aliases = aliases_for(team, custom)
st.caption("Aliases: " + ", ".join(aliases[:20]))

try:
    sports = list_sports(api_key, include_all=False)
except Exception as exc:
    st.error(safe_error(exc))
    st.stop()

ranked = sorted(sports, key=lambda s: sport_score(s, query), reverse=True)[: int(max_feeds)]
ranked = [SimpleNamespace(key="upcoming", title="Upcoming all sports", group="All", description="Upcoming games")] + ranked

if st.button(tr("scan"), type="primary"):
    all_events = []
    skipped = []
    progress = st.progress(0)
    status = st.empty()
    for idx, sport in enumerate(ranked):
        status.write(f"Scanning {sport.title}...")
        events, errors = scan_feed(api_key, sport.key, regions, int(max_events))
        all_events.extend(events)
        if errors and not events:
            skipped.append((sport.title, "; ".join(errors[:2])))
        progress.progress((idx + 1) / max(1, len(ranked)))
    status.empty()
    progress.empty()

    rows = []
    for event in all_events:
        score, matched = team_match(event, aliases)
        rows.append(snapshot(event, score, matched))

    team_rows = sorted([r for r in rows if r["_score"] >= 0.85], key=lambda r: (r["_score"], r["_prob"]), reverse=True)
    all_rows = sorted(rows, key=lambda r: r["_prob"], reverse=True)

    if not team_rows:
        st.error(f"{tr('selected')}: {selected_name} — {tr('no_team')}")
    else:
        st.success(f"{tr('selected')}: {selected_name} — {len(team_rows)} {tr('found')}")

    st.subheader("Team Market Finder Dashboard" if not IS_ES else "Panel del Buscador de Equipos")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Feeds scanned", len(ranked))
    c2.metric(tr("events"), len(rows))
    c3.metric(tr("found"), len(team_rows))
    c4.metric(tr("skipped"), len(skipped))

    tabs = st.tabs([tr("matches"), tr("general"), tr("diag")])
    with tabs[0]:
        if not team_rows:
            st.warning(tr("no_team"))
        else:
            for row in team_rows[:20]:
                show_event(row, expanded=row == team_rows[0])
    with tabs[1]:
        visible = [{k: v for k, v in r.items() if not k.startswith("_")} for r in all_rows]
        if visible:
            st.dataframe(visible, use_container_width=True, hide_index=True)
        else:
            st.info("No markets returned." if not IS_ES else "No se devolvieron mercados.")
    with tabs[2]:
        st.write(f"Strict team threshold: 85%")
        st.write(f"Selected team: {selected_name}")
        st.write(f"Aliases searched: {', '.join(aliases)}")
        st.write(f"Scanned feeds: {len(ranked)}")
        st.write(f"Returned markets: {len(rows)}")
        st.write(f"Selected-team markets found: {len(team_rows)}")
        if skipped:
            for title, reason in skipped[:50]:
                st.write(f"- {title}: {reason}")
