import os

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market
from autonomous_betting_agent.scorelines import estimate_scorelines, expected_goals_from_probability

st.title("Live market scanner")
st.caption("Scan one provider feed safely. If a feed or region is unavailable, the app shows a warning instead of crashing.")


def safe_error(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "Provider key was rejected. Check the key and plan access."
    if status == 422:
        return "This sport feed is not available for the selected market regions. Try us, uk, eu, or au."
    if status == 429:
        return "Provider quota or rate limit reached. Wait or use another key."
    return "Provider request failed. Try another feed or region."


def event_table(item):
    rows = []
    home_probability = None
    for outcome in item.outcomes:
        rows.append({
            "Outcome": outcome.name,
            "Price": round(outcome.average_price, 3),
            "Probability": f"{outcome.normalized_probability:.1%}",
            "Books": outcome.source_count,
        })
        if outcome.name == item.home_team:
            home_probability = outcome.normalized_probability
    return rows, home_probability


try:
    saved_token = str(st.secrets.get("THE_ODDS_API_KEY", ""))
except Exception:
    saved_token = os.getenv("THE_ODDS_API_KEY", "")

entry_token = st.text_input("Provider access token", value="", type="password")
key = entry_token.strip() or saved_token

if not key:
    st.info("Paste your own provider access token above. It is used only for this browser session unless the app owner configures one separately.")
    st.stop()

selected_regions = st.multiselect("Bookmaker market regions", ["us", "uk", "eu", "au"], default=["us", "eu", "uk"])
search_text = st.text_input("Sport search", "auto")
max_events = st.number_input("Max events", min_value=1, max_value=50, value=15, step=1)

if not selected_regions:
    st.error("Choose at least one market region.")
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
selected = st.selectbox("Sport feed", labels)
sport_key = choices[labels.index(selected)].key
region_text = ",".join(selected_regions)

if st.button("Scan", type="primary"):
    try:
        results = scan_market(key, sport_key, regions=region_text, max_events=int(max_events))
    except Exception as exc:
        st.warning(safe_error(exc))
        st.stop()

    if not results:
        st.info("No games with usable market data were returned for this feed.")
        st.stop()

    for item in results:
        st.subheader(f"{item.away_team} at {item.home_team}")
        st.write(f"Start: {item.commence_time}")
        st.success(f"Most likely: {item.favorite} ({item.favorite_probability:.1%})")
        rows, home_probability = event_table(item)
        st.dataframe(rows, use_container_width=True, hide_index=True)

        if home_probability is not None:
            home_xg, away_xg = expected_goals_from_probability(home_probability, neutral_site=False)
            score_rows = []
            for pick in estimate_scorelines(home_xg, away_xg):
                if pick.margin > 0:
                    margin = f"{item.home_team} by {pick.margin}"
                elif pick.margin < 0:
                    margin = f"{item.away_team} by {abs(pick.margin)}"
                else:
                    margin = "Draw"
                score_rows.append({"Score": pick.label, "Read": margin, "Estimated probability": f"{pick.probability:.1%}"})
            st.write("Most likely scorelines / spread")
            st.dataframe(score_rows, use_container_width=True, hide_index=True)
        else:
            st.caption("Scoreline estimates require a mapped home-team probability. This feed may use a two-outcome or non-team market.")

        st.caption("Market-based scan only. Add injuries, lineups, weather and team ratings before trusting a pick.")
