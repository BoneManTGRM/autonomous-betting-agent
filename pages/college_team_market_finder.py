import os
import unicodedata
from difflib import SequenceMatcher
from types import SimpleNamespace

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market

st.set_page_config(page_title="College Team Market Finder", layout="wide")

language = st.selectbox("Language / Idioma", ["English", "Español"], index=0)
IS_ES = language == "Español"

TEXT = {
    "title": {"English": "USA College Team Market Finder", "Español": "Buscador de Equipos Universitarios USA"},
    "caption": {
        "English": "Strict finder for U.S. college football and college basketball markets. Use the dropdown for built-in teams or type any school/team in Custom search. If the provider has no current odds market, the app says so instead of showing unrelated games.",
        "Español": "Buscador estricto para mercados de futbol americano universitario y baloncesto universitario de EE. UU. Usa el selector o escribe cualquier escuela/equipo en búsqueda manual. Si el proveedor no tiene mercado actual, la app lo dirá sin mostrar juegos sin relación.",
    },
    "token": {"English": "Provider key", "Español": "Clave del proveedor"},
    "sport": {"English": "College sport", "Español": "Deporte universitario"},
    "team": {"English": "Built-in team", "Español": "Equipo integrado"},
    "custom": {"English": "Custom school/team search", "Español": "Búsqueda manual de escuela/equipo"},
    "search": {"English": "Sport/feed search", "Español": "Buscar deporte/fuente"},
    "regions": {"English": "Bookmaker regions", "Español": "Regiones de casas"},
    "max_feeds": {"English": "Max feeds", "Español": "Máximo de fuentes"},
    "max_events": {"English": "Max events per feed", "Español": "Máximo de eventos por fuente"},
    "scan": {"English": "Search college team", "Español": "Buscar equipo universitario"},
    "dashboard": {"English": "College Team Finder Dashboard", "Español": "Panel del Buscador Universitario"},
    "selected": {"English": "Selected team", "Español": "Equipo seleccionado"},
    "no_team": {"English": "No current odds market was found for the selected college team. This usually means the provider did not return that school/team in current markets, not that the team is missing from the database.", "Español": "No se encontró mercado actual para el equipo universitario seleccionado. Normalmente significa que el proveedor no devolvió esa escuela/equipo en los mercados actuales, no que falte en la base de datos."},
    "feeds": {"English": "Feeds scanned", "Español": "Fuentes revisadas"},
    "events": {"English": "Markets returned", "Español": "Mercados devueltos"},
    "found": {"English": "Team markets found", "Español": "Mercados del equipo"},
    "skipped": {"English": "Skipped feeds", "Español": "Fuentes omitidas"},
    "matches": {"English": "Selected team matches", "Español": "Coincidencias del equipo"},
    "general": {"English": "General college markets found", "Español": "Mercados universitarios generales"},
    "diag": {"English": "Diagnostics", "Español": "Diagnóstico"},
    "lean": {"English": "Market lean", "Español": "Lectura de mercado"},
    "prob": {"English": "Probability", "Español": "Probabilidad"},
    "price": {"English": "Best price", "Español": "Mejor precio"},
    "quality": {"English": "Market data quality", "Español": "Calidad de datos"},
    "start": {"English": "Start", "Español": "Inicio"},
    "raw": {"English": "Raw market table", "Español": "Tabla cruda"},
    "matched": {"English": "Matched", "Español": "Coincidió"},
}

ALL_REGIONS = ["us", "us2", "uk", "eu", "au"]

# Built-in FBS and major college-basketball aliases. Custom search can be used for any school not listed here.
TEAM_DATA = [
    ("NCAAF", "Air Force Falcons", ["air force", "air force falcons", "falcons"]),
    ("NCAAF", "Akron Zips", ["akron", "akron zips", "zips"]),
    ("NCAAF", "Alabama Crimson Tide", ["alabama", "alabama crimson tide", "crimson tide", "bama"]),
    ("NCAAF", "Appalachian State Mountaineers", ["app state", "appalachian state", "appalachian state mountaineers", "mountaineers"]),
    ("NCAAF", "Arizona Wildcats", ["arizona", "arizona wildcats", "wildcats"]),
    ("NCAAF", "Arizona State Sun Devils", ["arizona state", "asu", "arizona state sun devils", "sun devils"]),
    ("NCAAF", "Arkansas Razorbacks", ["arkansas", "arkansas razorbacks", "razorbacks", "hogs"]),
    ("NCAAF", "Arkansas State Red Wolves", ["arkansas state", "arkansas state red wolves", "red wolves"]),
    ("NCAAF", "Army Black Knights", ["army", "army black knights", "black knights"]),
    ("NCAAF", "Auburn Tigers", ["auburn", "auburn tigers", "tigers"]),
    ("NCAAF", "Ball State Cardinals", ["ball state", "ball state cardinals", "cardinals"]),
    ("NCAAF", "Baylor Bears", ["baylor", "baylor bears", "bears"]),
    ("NCAAF", "Boise State Broncos", ["boise state", "boise state broncos", "broncos"]),
    ("NCAAF", "Boston College Eagles", ["boston college", "bc eagles", "boston college eagles", "eagles"]),
    ("NCAAF", "Bowling Green Falcons", ["bowling green", "bowling green falcons", "bgsu"]),
    ("NCAAF", "Buffalo Bulls", ["buffalo", "buffalo bulls", "bulls"]),
    ("NCAAF", "BYU Cougars", ["byu", "brigham young", "byu cougars", "cougars"]),
    ("NCAAF", "California Golden Bears", ["cal", "california", "california golden bears", "golden bears"]),
    ("NCAAF", "Central Michigan Chippewas", ["central michigan", "cmu", "central michigan chippewas", "chippewas"]),
    ("NCAAF", "Charlotte 49ers", ["charlotte", "charlotte 49ers", "49ers"]),
    ("NCAAF", "Cincinnati Bearcats", ["cincinnati", "cincinnati bearcats", "bearcats"]),
    ("NCAAF", "Clemson Tigers", ["clemson", "clemson tigers", "tigers"]),
    ("NCAAF", "Coastal Carolina Chanticleers", ["coastal carolina", "coastal carolina chanticleers", "chanticleers"]),
    ("NCAAF", "Colorado Buffaloes", ["colorado", "colorado buffaloes", "buffaloes", "buffs"]),
    ("NCAAF", "Colorado State Rams", ["colorado state", "colorado state rams", "rams"]),
    ("NCAAF", "Duke Blue Devils", ["duke", "duke blue devils", "blue devils"]),
    ("NCAAF", "East Carolina Pirates", ["east carolina", "ecu", "east carolina pirates", "pirates"]),
    ("NCAAF", "Eastern Michigan Eagles", ["eastern michigan", "emu", "eastern michigan eagles", "eagles"]),
    ("NCAAF", "Florida Gators", ["florida", "florida gators", "gators"]),
    ("NCAAF", "Florida Atlantic Owls", ["florida atlantic", "fau", "florida atlantic owls", "owls"]),
    ("NCAAF", "Florida International Panthers", ["fiu", "florida international", "fiu panthers", "panthers"]),
    ("NCAAF", "Florida State Seminoles", ["florida state", "fsu", "florida state seminoles", "seminoles"]),
    ("NCAAF", "Fresno State Bulldogs", ["fresno state", "fresno state bulldogs", "bulldogs"]),
    ("NCAAF", "Georgia Bulldogs", ["georgia", "georgia bulldogs", "bulldogs", "uga"]),
    ("NCAAF", "Georgia Southern Eagles", ["georgia southern", "georgia southern eagles", "eagles"]),
    ("NCAAF", "Georgia State Panthers", ["georgia state", "georgia state panthers", "panthers"]),
    ("NCAAF", "Georgia Tech Yellow Jackets", ["georgia tech", "gt", "georgia tech yellow jackets", "yellow jackets"]),
    ("NCAAF", "Hawaii Rainbow Warriors", ["hawaii", "hawai'i", "hawaii rainbow warriors", "rainbow warriors"]),
    ("NCAAF", "Houston Cougars", ["houston", "houston cougars", "cougars"]),
    ("NCAAF", "Illinois Fighting Illini", ["illinois", "illinois fighting illini", "fighting illini", "illini"]),
    ("NCAAF", "Indiana Hoosiers", ["indiana", "indiana hoosiers", "hoosiers"]),
    ("NCAAF", "Iowa Hawkeyes", ["iowa", "iowa hawkeyes", "hawkeyes"]),
    ("NCAAF", "Iowa State Cyclones", ["iowa state", "iowa state cyclones", "cyclones"]),
    ("NCAAF", "Jacksonville State Gamecocks", ["jacksonville state", "jacksonville state gamecocks", "gamecocks"]),
    ("NCAAF", "James Madison Dukes", ["james madison", "jmu", "james madison dukes", "dukes"]),
    ("NCAAF", "Kansas Jayhawks", ["kansas", "kansas jayhawks", "jayhawks"]),
    ("NCAAF", "Kansas State Wildcats", ["kansas state", "k state", "kansas state wildcats", "wildcats"]),
    ("NCAAF", "Kent State Golden Flashes", ["kent state", "kent state golden flashes", "golden flashes"]),
    ("NCAAF", "Kentucky Wildcats", ["kentucky", "kentucky wildcats", "wildcats"]),
    ("NCAAF", "Liberty Flames", ["liberty", "liberty flames", "flames"]),
    ("NCAAF", "Louisiana Ragin' Cajuns", ["louisiana", "ul lafayette", "ragin cajuns", "louisiana ragin cajuns"]),
    ("NCAAF", "Louisiana Tech Bulldogs", ["louisiana tech", "la tech", "louisiana tech bulldogs", "bulldogs"]),
    ("NCAAF", "Louisville Cardinals", ["louisville", "louisville cardinals", "cardinals"]),
    ("NCAAF", "LSU Tigers", ["lsu", "louisiana state", "lsu tigers", "tigers"]),
    ("NCAAF", "Marshall Thundering Herd", ["marshall", "marshall thundering herd", "thundering herd"]),
    ("NCAAF", "Maryland Terrapins", ["maryland", "maryland terrapins", "terrapins", "terps"]),
    ("NCAAF", "Memphis Tigers", ["memphis", "memphis tigers", "tigers"]),
    ("NCAAF", "Miami Hurricanes", ["miami hurricanes", "miami fl", "the u", "hurricanes"]),
    ("NCAAF", "Miami Ohio RedHawks", ["miami ohio", "miami oh", "miami redhawks", "redhawks"]),
    ("NCAAF", "Michigan Wolverines", ["michigan", "michigan wolverines", "wolverines"]),
    ("NCAAF", "Michigan State Spartans", ["michigan state", "msu spartans", "michigan state spartans", "spartans"]),
    ("NCAAF", "Middle Tennessee Blue Raiders", ["middle tennessee", "mtsu", "middle tennessee blue raiders", "blue raiders"]),
    ("NCAAF", "Minnesota Golden Gophers", ["minnesota", "minnesota golden gophers", "gophers"]),
    ("NCAAF", "Mississippi State Bulldogs", ["mississippi state", "miss state", "mississippi state bulldogs", "bulldogs"]),
    ("NCAAF", "Missouri Tigers", ["missouri", "mizzou", "missouri tigers", "tigers"]),
    ("NCAAF", "Navy Midshipmen", ["navy", "navy midshipmen", "midshipmen"]),
    ("NCAAF", "NC State Wolfpack", ["nc state", "north carolina state", "nc state wolfpack", "wolfpack"]),
    ("NCAAF", "Nebraska Cornhuskers", ["nebraska", "nebraska cornhuskers", "cornhuskers", "huskers"]),
    ("NCAAF", "Nevada Wolf Pack", ["nevada", "nevada wolf pack", "wolf pack"]),
    ("NCAAF", "New Mexico Lobos", ["new mexico", "new mexico lobos", "lobos"]),
    ("NCAAF", "New Mexico State Aggies", ["new mexico state", "nmsu", "new mexico state aggies", "aggies"]),
    ("NCAAF", "North Carolina Tar Heels", ["north carolina", "unc", "north carolina tar heels", "tar heels"]),
    ("NCAAF", "North Texas Mean Green", ["north texas", "unt", "north texas mean green", "mean green"]),
    ("NCAAF", "Northern Illinois Huskies", ["northern illinois", "niu", "northern illinois huskies", "huskies"]),
    ("NCAAF", "Northwestern Wildcats", ["northwestern", "northwestern wildcats", "wildcats"]),
    ("NCAAF", "Notre Dame Fighting Irish", ["notre dame", "notre dame fighting irish", "fighting irish"]),
    ("NCAAF", "Ohio Bobcats", ["ohio", "ohio bobcats", "bobcats"]),
    ("NCAAF", "Ohio State Buckeyes", ["ohio state", "osu buckeyes", "ohio state buckeyes", "buckeyes"]),
    ("NCAAF", "Oklahoma Sooners", ["oklahoma", "oklahoma sooners", "sooners"]),
    ("NCAAF", "Oklahoma State Cowboys", ["oklahoma state", "ok state", "oklahoma state cowboys", "cowboys"]),
    ("NCAAF", "Old Dominion Monarchs", ["old dominion", "odu", "old dominion monarchs", "monarchs"]),
    ("NCAAF", "Ole Miss Rebels", ["ole miss", "mississippi rebels", "ole miss rebels", "rebels"]),
    ("NCAAF", "Oregon Ducks", ["oregon", "oregon ducks", "ducks"]),
    ("NCAAF", "Oregon State Beavers", ["oregon state", "oregon state beavers", "beavers"]),
    ("NCAAF", "Penn State Nittany Lions", ["penn state", "penn state nittany lions", "nittany lions"]),
    ("NCAAF", "Pittsburgh Panthers", ["pitt", "pittsburgh", "pittsburgh panthers", "panthers"]),
    ("NCAAF", "Purdue Boilermakers", ["purdue", "purdue boilermakers", "boilermakers"]),
    ("NCAAF", "Rice Owls", ["rice", "rice owls", "owls"]),
    ("NCAAF", "Rutgers Scarlet Knights", ["rutgers", "rutgers scarlet knights", "scarlet knights"]),
    ("NCAAF", "Sam Houston Bearkats", ["sam houston", "sam houston state", "sam houston bearkats", "bearkats"]),
    ("NCAAF", "San Diego State Aztecs", ["san diego state", "sdsu", "san diego state aztecs", "aztecs"]),
    ("NCAAF", "San Jose State Spartans", ["san jose state", "sjsu", "san jose state spartans", "spartans"]),
    ("NCAAF", "SMU Mustangs", ["smu", "southern methodist", "smu mustangs", "mustangs"]),
    ("NCAAF", "South Alabama Jaguars", ["south alabama", "south alabama jaguars", "jaguars"]),
    ("NCAAF", "South Carolina Gamecocks", ["south carolina", "south carolina gamecocks", "gamecocks"]),
    ("NCAAF", "South Florida Bulls", ["south florida", "usf", "south florida bulls", "bulls"]),
    ("NCAAF", "Southern Miss Golden Eagles", ["southern miss", "southern miss golden eagles", "golden eagles"]),
    ("NCAAF", "Stanford Cardinal", ["stanford", "stanford cardinal", "cardinal"]),
    ("NCAAF", "Syracuse Orange", ["syracuse", "syracuse orange", "orange"]),
    ("NCAAF", "TCU Horned Frogs", ["tcu", "texas christian", "tcu horned frogs", "horned frogs"]),
    ("NCAAF", "Temple Owls", ["temple", "temple owls", "owls"]),
    ("NCAAF", "Tennessee Volunteers", ["tennessee", "tennessee volunteers", "volunteers", "vols"]),
    ("NCAAF", "Texas Longhorns", ["texas", "texas longhorns", "longhorns"]),
    ("NCAAF", "Texas A&M Aggies", ["texas a&m", "texas am", "texas a and m", "aggies"]),
    ("NCAAF", "Texas State Bobcats", ["texas state", "texas state bobcats", "bobcats"]),
    ("NCAAF", "Texas Tech Red Raiders", ["texas tech", "texas tech red raiders", "red raiders"]),
    ("NCAAF", "Toledo Rockets", ["toledo", "toledo rockets", "rockets"]),
    ("NCAAF", "Troy Trojans", ["troy", "troy trojans", "trojans"]),
    ("NCAAF", "Tulane Green Wave", ["tulane", "tulane green wave", "green wave"]),
    ("NCAAF", "Tulsa Golden Hurricane", ["tulsa", "tulsa golden hurricane", "golden hurricane"]),
    ("NCAAF", "UAB Blazers", ["uab", "alabama birmingham", "uab blazers", "blazers"]),
    ("NCAAF", "UCF Knights", ["ucf", "central florida", "ucf knights", "knights"]),
    ("NCAAF", "UCLA Bruins", ["ucla", "ucla bruins", "bruins"]),
    ("NCAAF", "UConn Huskies", ["uconn", "connecticut", "uconn huskies", "huskies"]),
    ("NCAAF", "UL Monroe Warhawks", ["ul monroe", "ulm", "louisiana monroe", "warhawks"]),
    ("NCAAF", "UMass Minutemen", ["umass", "massachusetts", "umass minutemen", "minutemen"]),
    ("NCAAF", "UNLV Rebels", ["unlv", "unlv rebels", "rebels"]),
    ("NCAAF", "USC Trojans", ["usc", "southern california", "usc trojans", "trojans"]),
    ("NCAAF", "Utah Utes", ["utah", "utah utes", "utes"]),
    ("NCAAF", "Utah State Aggies", ["utah state", "utah state aggies", "aggies"]),
    ("NCAAF", "UTEP Miners", ["utep", "texas el paso", "utep miners", "miners"]),
    ("NCAAF", "UTSA Roadrunners", ["utsa", "texas san antonio", "utsa roadrunners", "roadrunners"]),
    ("NCAAF", "Vanderbilt Commodores", ["vanderbilt", "vanderbilt commodores", "commodores"]),
    ("NCAAF", "Virginia Cavaliers", ["virginia", "uva", "virginia cavaliers", "cavaliers"]),
    ("NCAAF", "Virginia Tech Hokies", ["virginia tech", "vt hokies", "hokies"]),
    ("NCAAF", "Wake Forest Demon Deacons", ["wake forest", "wake forest demon deacons", "demon deacons"]),
    ("NCAAF", "Washington Huskies", ["washington huskies", "uw huskies", "huskies"]),
    ("NCAAF", "Washington State Cougars", ["washington state", "wazzu", "washington state cougars", "cougars"]),
    ("NCAAF", "West Virginia Mountaineers", ["west virginia", "wvu", "west virginia mountaineers", "mountaineers"]),
    ("NCAAF", "Western Kentucky Hilltoppers", ["western kentucky", "wku", "western kentucky hilltoppers", "hilltoppers"]),
    ("NCAAF", "Western Michigan Broncos", ["western michigan", "wmu", "western michigan broncos", "broncos"]),
    ("NCAAF", "Wisconsin Badgers", ["wisconsin", "wisconsin badgers", "badgers"]),
    ("NCAAF", "Wyoming Cowboys", ["wyoming", "wyoming cowboys", "cowboys"]),
    # Major/commonly listed NCAAB programs; custom search covers any other college team name.
    ("NCAAB", "Duke Blue Devils", ["duke", "duke blue devils", "blue devils"]),
    ("NCAAB", "North Carolina Tar Heels", ["north carolina", "unc", "tar heels", "north carolina tar heels"]),
    ("NCAAB", "Kansas Jayhawks", ["kansas", "kansas jayhawks", "jayhawks"]),
    ("NCAAB", "Kentucky Wildcats", ["kentucky", "kentucky wildcats", "wildcats"]),
    ("NCAAB", "UConn Huskies", ["uconn", "connecticut", "uconn huskies", "huskies"]),
    ("NCAAB", "Gonzaga Bulldogs", ["gonzaga", "gonzaga bulldogs", "bulldogs"]),
    ("NCAAB", "Houston Cougars", ["houston", "houston cougars", "cougars"]),
    ("NCAAB", "Purdue Boilermakers", ["purdue", "purdue boilermakers", "boilermakers"]),
    ("NCAAB", "Arizona Wildcats", ["arizona", "arizona wildcats", "wildcats"]),
    ("NCAAB", "Baylor Bears", ["baylor", "baylor bears", "bears"]),
    ("NCAAB", "Villanova Wildcats", ["villanova", "villanova wildcats", "wildcats"]),
    ("NCAAB", "Michigan State Spartans", ["michigan state", "msu", "michigan state spartans", "spartans"]),
    ("NCAAB", "Indiana Hoosiers", ["indiana", "indiana hoosiers", "hoosiers"]),
    ("NCAAB", "UCLA Bruins", ["ucla", "ucla bruins", "bruins"]),
    ("NCAAB", "Alabama Crimson Tide", ["alabama", "alabama crimson tide", "crimson tide", "bama"]),
    ("NCAAB", "Tennessee Volunteers", ["tennessee", "tennessee volunteers", "vols", "volunteers"]),
    ("NCAAB", "Auburn Tigers", ["auburn", "auburn tigers", "tigers"]),
    ("NCAAB", "Marquette Golden Eagles", ["marquette", "marquette golden eagles", "golden eagles"]),
    ("NCAAB", "Creighton Bluejays", ["creighton", "creighton bluejays", "bluejays"]),
    ("NCAAB", "Texas Longhorns", ["texas", "texas longhorns", "longhorns"]),
    ("NCAAB", "Arkansas Razorbacks", ["arkansas", "arkansas razorbacks", "razorbacks"]),
    ("NCAAB", "Memphis Tigers", ["memphis", "memphis tigers", "tigers"]),
    ("NCAAB", "San Diego State Aztecs", ["san diego state", "sdsu", "aztecs"]),
    ("NCAAB", "St. John's Red Storm", ["st johns", "st. johns", "st john's", "st. john's", "red storm"]),
]


def tr(key):
    return TEXT.get(key, {}).get(language) or TEXT.get(key, {}).get("English") or key


def clean(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.lower().replace("-", " ").replace(".", " ").replace("'", "").replace("&", " and ").split())


def aliases_for(team_name, custom):
    if custom.strip():
        base = clean(custom)
        aliases = {base}
        for _, _, values in TEAM_DATA:
            cleaned = [clean(v) for v in values]
            if base in cleaned:
                aliases.update(cleaned)
        return sorted(aliases)
    for _, name, values in TEAM_DATA:
        if name == team_name:
            return sorted(clean(v) for v in values)
    return []


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


def sport_score(sport, sport_filter, query):
    text = clean(f"{sport.key} {sport.group} {sport.title} {sport.description}")
    score = 0.0
    sport_terms = {
        "NCAAF": ["americanfootball_ncaaf", "ncaaf", "college football", "americanfootball"],
        "NCAAB": ["basketball_ncaab", "ncaab", "college basketball", "basketball"],
        "All": ["americanfootball_ncaaf", "ncaaf", "college football", "basketball_ncaab", "ncaab", "college basketball"],
    }[sport_filter]
    for term in sport_terms:
        if clean(term) in text:
            score += 25
    for word in [clean(w) for w in query.split() if clean(w)]:
        if word in text:
            score += 8
    if any(w in text for w in ["winner", "championship", "outright"]):
        score -= 20
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


def snapshot(event, score, matched):
    top = event.outcomes[0]
    second = event.outcomes[1] if len(event.outcomes) > 1 else None
    gap = top.normalized_probability - (second.normalized_probability if second else 0)
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
    return [{
        "Outcome": o.name,
        "Average price": round(o.average_price, 3),
        "Best price": round((getattr(o, "best_price", None) or o.average_price), 3),
        "Best book": getattr(o, "best_bookmaker", None) or "",
        "Probability": f"{o.normalized_probability:.1%}",
        "Books": o.source_count,
    } for o in event.outcomes]


def show_event(row, expanded=False):
    event = row["_event"]
    with st.expander(f"{row['Event']} | {row['Market lean']} {row['Probability']} | Match {row['Match']}", expanded=expanded):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(tr("lean"), row["Market lean"])
        c2.metric(tr("prob"), row["Probability"])
        c3.metric(tr("price"), row["Best price"])
        c4.metric(tr("quality"), f"{row['Market data quality']}/100")
        st.write(f"{tr('start')}: {row['Start']}")
        st.write(f"{tr('matched')}: {row['Matched']}")
        with st.expander(tr("raw")):
            st.dataframe(market_table(event), use_container_width=True, hide_index=True)


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

sport_filter = st.selectbox(tr("sport"), ["NCAAF", "NCAAB", "All"], index=0)
teams = [name for sport, name, _ in TEAM_DATA if sport_filter == "All" or sport == sport_filter]
team = st.selectbox(tr("team"), teams)
custom = st.text_input(tr("custom"), "")
default_query = {"NCAAF": "college football ncaaf", "NCAAB": "college basketball ncaab", "All": "college football basketball ncaaf ncaab"}[sport_filter]
query = st.text_input(tr("search"), default_query)
regions = st.multiselect(tr("regions"), ALL_REGIONS, default=["us", "eu", "uk"])
max_feeds = st.number_input(tr("max_feeds"), min_value=1, max_value=100, value=50)
max_events = st.number_input(tr("max_events"), min_value=1, max_value=50, value=50)

aliases = aliases_for(team, custom)
st.caption("Aliases: " + ", ".join(aliases[:20]))

try:
    sports = list_sports(api_key, include_all=False)
except Exception as exc:
    st.error(safe_error(exc))
    st.stop()

ranked = sorted(sports, key=lambda s: sport_score(s, sport_filter, query), reverse=True)[: int(max_feeds)]
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
        st.error(f"{tr('selected')}: {custom.strip() or team} — {tr('no_team')}")
    else:
        st.success(f"{tr('selected')}: {custom.strip() or team} — {len(team_rows)} {tr('found')}")

    st.subheader(tr("dashboard"))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(tr("feeds"), len(ranked))
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
        st.write(f"Selected sport: {sport_filter}")
        st.write(f"Selected team: {custom.strip() or team}")
        st.write(f"Aliases searched: {', '.join(aliases)}")
        st.write(f"Scanned feeds: {len(ranked)}")
        st.write(f"Returned markets: {len(rows)}")
        st.write(f"Selected-team markets found: {len(team_rows)}")
        if skipped:
            for title, reason in skipped[:50]:
                st.write(f"- {title}: {reason}")
