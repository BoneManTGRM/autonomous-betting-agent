import csv
import io
import os
import unicodedata
from difflib import SequenceMatcher
from types import SimpleNamespace

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market

st.set_page_config(page_title="Combat Sports Fighter Finder", layout="wide")

language = st.selectbox("Translate page", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "Combat Sports Fighter Finder", "Español": "Buscador de Peleadores"},
    "caption": {
        "English": "Boxing, UFC, and MMA moneyline finder. It scans provider-returned combat markets and uses strict fighter matching so unrelated events are not treated as matches.",
        "Español": "Buscador de ganador/moneyline para boxeo, UFC y MMA. Escanea mercados de combate devueltos por el proveedor y usa coincidencia estricta de peleadores para no mostrar eventos sin relación.",
    },
    "token": {"English": "Provider key", "Español": "Clave del proveedor"},
    "mode": {"English": "Search mode", "Español": "Modo de búsqueda"},
    "all": {"English": "All combat markets", "Español": "Todos los mercados de combate"},
    "fighter": {"English": "One fighter", "Español": "Un peleador"},
    "fighter_name": {"English": "Fighter name", "Español": "Nombre del peleador"},
    "preset": {"English": "Known fighter shortcut", "Español": "Atajo de peleador conocido"},
    "regions": {"English": "Bookmaker regions", "Español": "Regiones de casas de apuesta"},
    "max_feeds": {"English": "Max feeds", "Español": "Máximo de feeds"},
    "max_events": {"English": "Max events per feed", "Español": "Máximo de eventos por feed"},
    "scan": {"English": "Scan combat markets", "Español": "Escanear mercados de combate"},
    "no_data": {"English": "No combat sports odds markets were returned. Try more regions, leave the fighter blank, or check whether the provider currently has boxing/UFC markets.", "Español": "No se devolvieron mercados de combate. Prueba más regiones, deja el peleador vacío o revisa si el proveedor tiene mercados de boxeo/UFC ahora mismo."},
    "no_match": {"English": "No current market matched that fighter. This usually means the provider did not return that fighter in the scanned markets right now.", "Español": "Ningún mercado actual coincidió con ese peleador. Normalmente significa que el proveedor no devolvió a ese peleador en los mercados escaneados ahora mismo."},
    "dashboard": {"English": "Combat dashboard", "Español": "Panel de combate"},
    "matches": {"English": "Fighter matches", "Español": "Coincidencias del peleador"},
    "all_markets": {"English": "All combat markets", "Español": "Todos los mercados de combate"},
    "diagnostics": {"English": "Diagnostics", "Español": "Diagnóstico"},
    "pick": {"English": "Market lean", "Español": "Lectura del mercado"},
    "prob": {"English": "No-vig probability", "Español": "Probabilidad sin margen"},
    "price": {"English": "Best price", "Español": "Mejor momio"},
    "quality": {"English": "Data quality", "Español": "Calidad de datos"},
    "start": {"English": "Start", "Español": "Inicio"},
    "moneyline": {"English": "Moneyline", "Español": "Ganador / moneyline"},
    "feeds_scanned": {"English": "Feeds scanned", "Español": "Feeds escaneados"},
    "markets_returned": {"English": "Markets returned", "Español": "Mercados devueltos"},
    "fighter_markets": {"English": "Fighter markets found", "Español": "Mercados del peleador"},
    "skipped": {"English": "Skipped feeds", "Español": "Feeds omitidos"},
    "not_available": {"English": "Not available", "Español": "No disponible"},
    "note": {"English": "Custom fighter search works for any fighter name returned by the odds provider. The preset list only adds common aliases; it is not meant to be every fighter who exists.", "Español": "La búsqueda manual funciona con cualquier peleador que el proveedor devuelva. La lista de atajos solo agrega alias comunes; no pretende incluir a todos los peleadores que existen."},
    "download": {"English": "Download CSV", "Español": "Descargar CSV"},
    "feeds_found": {"English": "Dedicated combat feeds found", "Español": "Feeds dedicados de combate encontrados"},
    "markets_requested": {"English": "Markets requested: h2h/moneyline only. This avoids failures because boxing and MMA feeds often do not support spread/total markets.", "Español": "Mercados solicitados: solo ganador/moneyline. Esto evita fallas porque los feeds de boxeo y MMA normalmente no aceptan spread/total."},
    "aliases_used": {"English": "Aliases used", "Español": "Alias usados"},
    "custom_note": {"English": "Manual fighter search is the real coverage layer. Presets are shortcuts.", "Español": "La búsqueda manual es la cobertura real. Los atajos solo facilitan nombres comunes."},
}

ALL_REGIONS = ["us", "us2", "uk", "eu", "au"]

FIGHTER_ALIASES = {
    "Canelo Alvarez": ["canelo", "canelo alvarez", "saul alvarez", "saúl álvarez"],
    "Terence Crawford": ["terence crawford", "crawford", "bud crawford", "bud"],
    "Oleksandr Usyk": ["oleksandr usyk", "usyk"],
    "Tyson Fury": ["tyson fury", "fury", "gypsy king"],
    "Anthony Joshua": ["anthony joshua", "joshua", "aj"],
    "Gervonta Davis": ["gervonta davis", "tank davis", "tank"],
    "Ryan Garcia": ["ryan garcia", "king ry"],
    "Devin Haney": ["devin haney", "haney"],
    "Shakur Stevenson": ["shakur stevenson", "shakur"],
    "Naoya Inoue": ["naoya inoue", "inoue", "monster"],
    "David Benavidez": ["david benavidez", "benavidez", "mexican monster"],
    "Artur Beterbiev": ["artur beterbiev", "beterbiev"],
    "Dmitry Bivol": ["dmitry bivol", "bivol"],
    "Alex Pereira": ["alex pereira", "poatan"],
    "Jon Jones": ["jon jones", "bones jones", "bones"],
    "Tom Aspinall": ["tom aspinall", "aspinall"],
    "Islam Makhachev": ["islam makhachev", "makhachev"],
    "Ilia Topuria": ["ilia topuria", "topuria", "el matador"],
    "Sean O'Malley": ["sean o'malley", "sean omalley", "omalley", "sugar sean"],
    "Khamzat Chimaev": ["khamzat chimaev", "chimaev", "borz"],
    "Israel Adesanya": ["israel adesanya", "adesanya", "izzy", "stylebender"],
    "Max Holloway": ["max holloway", "holloway", "blessed"],
    "Alexander Volkanovski": ["alexander volkanovski", "volkanovski", "volk"],
    "Charles Oliveira": ["charles oliveira", "oliveira", "do bronx"],
    "Dustin Poirier": ["dustin poirier", "poirier", "diamond"],
    "Justin Gaethje": ["justin gaethje", "gaethje", "highlight"],
    "Conor McGregor": ["conor mcgregor", "mcgregor", "notorious"],
}


def t(key: str) -> str:
    return TEXT.get(key, {}).get(language) or TEXT.get(key, {}).get("English") or key


def clean(value: str) -> str:
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return " ".join(value.lower().replace("-", " ").replace(".", " ").replace("'", "").split())


def fighter_aliases(value: str) -> list[str]:
    base = clean(value)
    aliases = {base}
    for key, names in FIGHTER_ALIASES.items():
        cleaned = [clean(name) for name in names]
        if base == clean(key) or base in cleaned:
            aliases.update(cleaned)
    return sorted(alias for alias in aliases if alias)


def match_score(filter_text, event):
    if not filter_text.strip():
        return 1.0, "all"
    aliases = fighter_aliases(filter_text)
    names = [event.home_team, event.away_team] + [outcome.name for outcome in event.outcomes]
    best = 0.0
    matched = ""
    for alias in aliases:
        for name in names:
            a, n = clean(alias), clean(name)
            if not a or not n:
                score = 0.0
            elif a in n or n in a:
                score = 1.0
            else:
                ratio = SequenceMatcher(None, a, n).ratio()
                score = ratio if ratio >= 0.88 else 0.0
            if score > best:
                best = score
                matched = f"{alias} -> {name}"
    return best, matched


def safe_error(exc):
    status = getattr(getattr(exc, "response", None), "status_code", None)
    if status in (401, 403):
        return "clave rechazada" if IS_ES else "key rejected"
    if status == 422:
        return "feed o región no disponible" if IS_ES else "feed or region unavailable"
    if status == 429:
        return "límite de cuota o velocidad" if IS_ES else "quota/rate limit"
    return "falló la solicitud" if IS_ES else "request failed"


def is_combat_sport(sport):
    text = clean(f"{sport.key} {sport.group} {sport.title} {sport.description}")
    combat_terms = ["boxing", "box", "ufc", "mma", "mixed martial", "pfl", "bellator", "combat", "fight"]
    return any(term in text for term in combat_terms) and not any(term in text for term in ["winner", "championship", "outright"])


def combat_score(sport):
    text = clean(f"{sport.key} {sport.group} {sport.title} {sport.description}")
    return sum(10 for term in ["ufc", "mma", "boxing", "mixed martial", "pfl", "bellator", "fight"] if term in text)


def scan_feed(api_key, sport_key, regions, max_events):
    attempts = [",".join(regions)] + list(regions)
    seen = set()
    results = []
    errors = []
    for region in attempts:
        if not region:
            continue
        try:
            events = scan_market(api_key, sport_key, regions=region, max_events=max_events, markets="h2h")
            for event in events:
                key = event.event_id or f"{event.sport_key}:{event.home_team}:{event.away_team}:{event.commence_time}"
                if key not in seen:
                    seen.add(key)
                    results.append(event)
            if results:
                return results, errors
        except Exception as exc:
            errors.append(f"{region}: {safe_error(exc)}")
    return results, errors


def snapshot(event, score, matched):
    top = event.outcomes[0]
    second = event.outcomes[1] if len(event.outcomes) > 1 else None
    gap = top.normalized_probability - (second.normalized_probability if second else 0)
    max_range = max((outcome.price_range or 0.0) for outcome in event.outcomes)
    quality = max(0, min(100, round(45 + min(event.bookmaker_count, 12) * 3.5 + min(gap, 0.30) * 80 - min(max_range, 1.5) * 6)))
    return {
        "Event": f"{event.away_team} at {event.home_team}",
        "Sport": event.sport_title,
        "Start": event.commence_time,
        "Pick": top.name,
        "No-vig probability": f"{top.normalized_probability:.1%}",
        "Best price": round((top.best_price or top.average_price), 3),
        "Best book": top.best_bookmaker or "",
        "Books": event.bookmaker_count,
        "Data quality": quality,
        "Match": f"{score:.0%}",
        "Matched": matched,
        "_score": score,
        "_prob": top.normalized_probability,
        "_event": event,
    }


def market_table(event):
    return [{
        "Outcome": outcome.name,
        "Average price": round(outcome.average_price, 3),
        "Best price": round((outcome.best_price or outcome.average_price), 3),
        "Best book": outcome.best_bookmaker or "",
        "No-vig probability": f"{outcome.normalized_probability:.1%}",
        "Books": outcome.source_count,
    } for outcome in event.outcomes]


def show_event(row, expanded=False):
    event = row["_event"]
    with st.expander(f"{row['Event']} | {row['Pick']} {row['No-vig probability']} | Q{row['Data quality']}", expanded=expanded):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("pick"), row["Pick"])
        c2.metric(t("prob"), row["No-vig probability"])
        c3.metric(t("price"), row["Best price"])
        c4.metric(t("quality"), f"{row['Data quality']}/100")
        st.write(f"{t('start')}: {row['Start']}")
        if row["Matched"]:
            st.write(f"Matched: {row['Matched']}")
        with st.expander(t("moneyline"), expanded=True):
            st.dataframe(market_table(event), use_container_width=True, hide_index=True)


def csv_text(rows):
    visible = [{k: v for k, v in row.items() if not k.startswith("_")} for row in rows]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(visible[0].keys()))
    writer.writeheader()
    writer.writerows(visible)
    return output.getvalue()


st.title(t("title"))
st.caption(t("caption"))
st.info(t("note"))

try:
    saved_key = str(st.secrets.get("THE_ODDS_API_KEY", ""))
except Exception:
    saved_key = os.getenv("THE_ODDS_API_KEY", "")

api_key = st.text_input(t("token"), type="password").strip() or saved_key
if not api_key:
    st.info("Paste your provider key." if not IS_ES else "Pega tu clave del proveedor.")
    st.stop()

mode = st.radio(t("mode"), [t("all"), t("fighter")], horizontal=True)
known_names = [""] + sorted(FIGHTER_ALIASES.keys())
preset = st.selectbox(t("preset"), known_names, index=0)
manual = st.text_input(t("fighter_name"), preset)
fighter_query = manual.strip() if mode == t("fighter") else ""
regions = st.multiselect(t("regions"), ALL_REGIONS, default=["us", "eu", "uk"])
max_feeds = st.number_input(t("max_feeds"), min_value=1, max_value=80, value=40, step=1)
max_events = st.number_input(t("max_events"), min_value=1, max_value=50, value=50, step=1)

try:
    sports = list_sports(api_key, include_all=False)
except Exception as exc:
    st.error(safe_error(exc))
    st.stop()

combat_sports = sorted([sport for sport in sports if is_combat_sport(sport)], key=combat_score, reverse=True)
selected_sports = [SimpleNamespace(key="upcoming", title="Upcoming all sports", group="All", description="Upcoming games")] + combat_sports[: int(max_feeds)]
st.caption(f"{t('feeds_found')}: " + (", ".join([sport.title for sport in combat_sports]) if combat_sports else t("not_available")))

if st.button(t("scan"), type="primary"):
    all_events = []
    skipped = []
    progress = st.progress(0)
    status = st.empty()
    for index, sport in enumerate(selected_sports):
        status.write(("Escaneando" if IS_ES else "Scanning") + f" {sport.title}...")
        events, errors = scan_feed(api_key, sport.key, regions, int(max_events))
        for event in events:
            event_text = clean(f"{event.sport_key} {event.sport_title} {event.home_team} {event.away_team} " + " ".join([outcome.name for outcome in event.outcomes]))
            if sport.key == "upcoming" and not any(term in event_text for term in ["ufc", "mma", "boxing", "box", "fight", "pfl", "bellator"]):
                continue
            all_events.append(event)
        if errors and not events:
            skipped.append((sport.title, "; ".join(errors[:2])))
        progress.progress((index + 1) / max(1, len(selected_sports)))
    status.empty()
    progress.empty()

    rows = []
    for event in all_events:
        score, matched = match_score(fighter_query, event)
        rows.append(snapshot(event, score, matched))

    if fighter_query:
        fighter_rows = [row for row in rows if row["_score"] >= 0.85]
        if not fighter_rows:
            st.warning(t("no_match"))
            display_rows = []
        else:
            display_rows = fighter_rows
    else:
        display_rows = rows

    display_rows = sorted(display_rows, key=lambda row: (row["_score"], row["_prob"], row["Data quality"]), reverse=True)

    if not display_rows:
        st.error(t("no_data"))
        if skipped:
            with st.expander(t("skipped"), expanded=True):
                for title, reason in skipped[:60]:
                    st.write(f"- {title}: {reason}")
        st.stop()

    st.subheader(t("dashboard"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("feeds_scanned"), len(selected_sports))
    c2.metric(t("markets_returned"), len(rows))
    c3.metric(t("fighter_markets"), len(display_rows))
    c4.metric(t("skipped"), len(skipped))

    st.download_button(t("download"), data=csv_text(display_rows), file_name="combat_sports_fighter_finder.csv", mime="text/csv")

    tabs = st.tabs([t("matches"), t("all_markets"), t("diagnostics")])
    with tabs[0]:
        for row in display_rows[:30]:
            show_event(row, expanded=row == display_rows[0])
    with tabs[1]:
        st.dataframe([{k: v for k, v in row.items() if not k.startswith("_")} for row in rows], use_container_width=True, hide_index=True)
    with tabs[2]:
        st.write(t("markets_requested"))
        st.write(t("custom_note"))
        st.write("Combat feeds: " + (", ".join([sport.title for sport in combat_sports]) if combat_sports else t("not_available")))
        st.write("Scanned: upcoming + dedicated combat feeds.")
        if fighter_query:
            st.write(f"{t('aliases_used')}: " + ", ".join(fighter_aliases(fighter_query)))
        if skipped:
            for title, reason in skipped[:60]:
                st.write(f"- {title}: {reason}")
