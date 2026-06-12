from __future__ import annotations

import streamlit as st

from autonomous_betting_agent import AutonomousBettingAgent, EventResearchInput, TeamSnapshot
from autonomous_betting_agent.output import render_text


st.set_page_config(page_title="Autonomous Betting Agent", layout="wide")
st.title("Autonomous Betting Agent")
st.caption("Research-only sports probability estimates using an ARA/TGRM-style workflow.")

sport = st.text_input("Sport", "basketball")
event_name = st.text_input("Event name", "Example City Hawks vs Example Valley Wolves")
neutral_site = st.checkbox("Neutral site", value=False)

col_home, col_away = st.columns(2)

with col_home:
    st.subheader("Home side")
    home = TeamSnapshot(
        name=st.text_input("Home name", "Example City Hawks"),
        rating=st.number_input("Home rating", value=1580.0),
        recent_form=st.slider("Home recent form", -1.0, 1.0, 0.45),
        injury_impact=st.slider("Home injury impact", 0.0, 1.0, 0.10),
        rest_advantage=st.slider("Home rest advantage", -1.0, 1.0, 0.25),
        matchup_edge=st.slider("Home matchup edge", -1.0, 1.0, 0.20),
        weather_fit=st.slider("Home conditions fit", -1.0, 1.0, 0.0),
        data_completeness=st.slider("Home data completeness", 0.0, 1.0, 0.92),
        source_count=st.number_input("Home source count", min_value=0, value=6),
    )

with col_away:
    st.subheader("Away side")
    away = TeamSnapshot(
        name=st.text_input("Away name", "Example Valley Wolves"),
        rating=st.number_input("Away rating", value=1530.0),
        recent_form=st.slider("Away recent form", -1.0, 1.0, 0.15),
        injury_impact=st.slider("Away injury impact", 0.0, 1.0, 0.25),
        rest_advantage=st.slider("Away rest advantage", -1.0, 1.0, -0.10),
        matchup_edge=st.slider("Away matchup edge", -1.0, 1.0, -0.05),
        weather_fit=st.slider("Away conditions fit", -1.0, 1.0, 0.0),
        data_completeness=st.slider("Away data completeness", 0.0, 1.0, 0.88),
        source_count=st.number_input("Away source count", min_value=0, value=5),
    )

home_price = st.number_input("Home market price", min_value=1.01, value=1.80)
away_price = st.number_input("Away market price", min_value=1.01, value=2.10)

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
