import streamlit as st

from autonomous_betting_agent import AutonomousBettingAgent, EventResearchInput, TeamSnapshot
from autonomous_betting_agent.output import render_text
from autonomous_betting_agent.scorelines import estimate_scorelines, expected_goals_from_probability

st.set_page_config(page_title="Autonomous Betting Agent", layout="wide")
st.title("Autonomous Betting Agent")
st.caption("Research-only sports probability estimates using an ARA/TGRM-style workflow.")
st.info("Use the Streamlit sidebar menu to open the Live Market Scanner page. On mobile, tap the arrow/menu control to show the sidebar.")

sport = st.text_input("Sport", "soccer")
event_name = st.text_input("Event name", "Team A vs Team B")
neutral_site = st.checkbox("Neutral site", value=False)

col_home, col_away = st.columns(2)

with col_home:
    st.subheader("Home side")
    home = TeamSnapshot(
        name=st.text_input("Home name", "Team A"),
        rating=st.number_input("Home rating", value=1580.0),
        recent_form=st.slider("Home recent form", -1.0, 1.0, 0.25),
        injury_impact=st.slider("Home injury impact", 0.0, 1.0, 0.10),
        rest_advantage=st.slider("Home rest advantage", -1.0, 1.0, 0.10),
        matchup_edge=st.slider("Home matchup edge", -1.0, 1.0, 0.10),
        weather_fit=st.slider("Home conditions fit", -1.0, 1.0, 0.0),
        data_completeness=st.slider("Home data completeness", 0.0, 1.0, 0.80),
        source_count=st.number_input("Home source count", min_value=0, value=5),
    )

with col_away:
    st.subheader("Away side")
    away = TeamSnapshot(
        name=st.text_input("Away name", "Team B"),
        rating=st.number_input("Away rating", value=1530.0),
        recent_form=st.slider("Away recent form", -1.0, 1.0, 0.05),
        injury_impact=st.slider("Away injury impact", 0.0, 1.0, 0.20),
        rest_advantage=st.slider("Away rest advantage", -1.0, 1.0, 0.0),
        matchup_edge=st.slider("Away matchup edge", -1.0, 1.0, -0.05),
        weather_fit=st.slider("Away conditions fit", -1.0, 1.0, 0.0),
        data_completeness=st.slider("Away data completeness", 0.0, 1.0, 0.80),
        source_count=st.number_input("Away source count", min_value=0, value=5),
    )

home_price = st.number_input("Home market price", min_value=1.01, value=1.80)
away_price = st.number_input("Away market price", min_value=1.01, value=2.10)

st.subheader("Scoreline settings")
use_manual_xg = st.checkbox("Use manual expected goals", value=False)
if use_manual_xg:
    home_xg = st.number_input("Home expected goals", min_value=0.05, max_value=8.0, value=1.45)
    away_xg = st.number_input("Away expected goals", min_value=0.05, max_value=8.0, value=1.10)
else:
    home_xg = None
    away_xg = None

if st.button("Analyze event"):
    event = EventResearchInput(
        sport=sport,
        event_name=event_name,
        home=home,
        away=away,
        neutral_site=neutral_site,
        home_market_price=home_price,
        away_market_price=away_price,
    )
    result = AutonomousBettingAgent().analyze(event)
    st.text(render_text(result))
    st.json(result.__dict__)

    if home_xg is None or away_xg is None:
        home_xg, away_xg = expected_goals_from_probability(result.home_probability, neutral_site)

    st.subheader("Most likely scorelines / spread")
    st.write(f"Estimated goals: {home.name} {home_xg:.2f}, {away.name} {away_xg:.2f}")
    score_rows = []
    for pick in estimate_scorelines(home_xg, away_xg):
        if pick.margin > 0:
            spread = f"{home.name} by {pick.margin}"
        elif pick.margin < 0:
            spread = f"{away.name} by {abs(pick.margin)}"
        else:
            spread = "Draw"
        score_rows.append({"Score": pick.label, "Spread": spread, "Probability": f"{pick.probability:.1%}"})
    st.dataframe(score_rows, use_container_width=True, hide_index=True)
    st.warning("Exact scores are much harder than winner probabilities. Treat this as a rough research estimate, not a guarantee.")
