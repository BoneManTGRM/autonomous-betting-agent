import os

import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market

st.title("Live market scanner")

try:
    key = str(st.secrets.get("THE_ODDS_API_KEY", ""))
except Exception:
    key = os.getenv("THE_ODDS_API_KEY", "")

if not key:
    st.info("Add THE_ODDS_API_KEY in Streamlit secrets.")
else:
    region_text = st.text_input("Regions", "us,eu,uk")
    search_text = st.text_input("Sport search", "soccer")
    max_events = st.slider("Max events", 1, 50, 15)
    sports = list_sports(key, include_all=False)
    terms = [x.lower() for x in search_text.split() if x.strip()]
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
    if st.button("Scan"):
        results = scan_market(key, sport_key, regions=region_text, max_events=max_events)
        for item in results:
            st.subheader(f"{item.away_team} at {item.home_team}")
            st.write(f"Most likely: {item.favorite} ({item.favorite_probability:.1%})")
            rows = []
            for outcome in item.outcomes:
                rows.append({"Outcome": outcome.name, "Price": round(outcome.average_price, 3), "Probability": f"{outcome.normalized_probability:.1%}"})
            st.dataframe(rows, use_container_width=True, hide_index=True)
