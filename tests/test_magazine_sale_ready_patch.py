from __future__ import annotations

from autonomous_betting_agent.magazine_sale_ready_patch import (
    sale_ready_injury_items,
    sale_ready_matchup_items,
    sale_ready_recommendation,
    sale_ready_team_items,
)


def _row(**overrides):
    row = {
        "event_name": "Iraq vs France",
        "away_team": "Iraq",
        "home_team": "France",
        "sport": "FIFA WORLD CUP",
        "pick": "Game total: Over 2.5",
        "final_decision": "PLAY SMALL",
        "model_market_edge": "-0.021",
        "expected_value_per_unit": "-0.029",
        "sportsdataio_team_summary": "SDIO checked; no provider event ID in row.",
        "api_football_summary": "API-FB lookup checked Iraq / France; no match returned.",
        "api_football_team_summary": "API-FB lookup checked Iraq / France; no match returned.",
        "newsapi_summary": "News checked; no injury/lineup headline.",
        "news_injury_summary": "News checked; no injury/lineup headline.",
        "weather_summary": "Weather: Partly cloudy, 23.3°C, wind 5.8 kph. Partly cloudy, 23.3°C, wind 5.8 kph. Location: Philadelphia, Pennsylvania, United States of America.",
        "api_sources_active": "SportsDataIO|WeatherAPI|API-Football|NewsAPI",
        "api_sources_inactive": "Perplexity",
        "odds_source": "The Odds API",
    }
    row.update(overrides)
    return row


def test_negative_edge_or_ev_cannot_play_small():
    action, explanation, playable = sale_ready_recommendation(_row())

    assert action == "WATCHLIST"
    assert playable is False
    assert "Do not play" in explanation
    assert action != "PLAY SMALL"


def test_positive_thin_edge_can_play_small():
    action, _explanation, playable = sale_ready_recommendation(
        _row(model_market_edge="0.010", expected_value_per_unit="0.010")
    )

    assert action == "PLAY SMALL"
    assert playable is True


def test_team_and_injury_fallbacks_are_professional_and_compact():
    team_items = sale_ready_team_items(_row(), "away")
    injury_items = sale_ready_injury_items(_row(), "away")
    text = "\n".join(team_items + injury_items)

    assert "No SDIO event ID returned." in team_items
    assert "No lineup/injury headline returned." in text
    assert "SDIO checked; no provider event ID in row." not in text
    assert "News checked; no injury/lineup headline." not in text
    assert "team lookup matched" not in text


def test_matchup_weather_location_and_api_fb_are_compact():
    items = sale_ready_matchup_items(_row())
    text = "\n".join(items)

    assert "Weather: 23.3°C, partly cloudy, wind 5.8 kph." in items
    assert "Location: Philadelphia, PA, USA." in items
    assert "API-FB lookup checked; no fixture match." in items
    assert text.count("Partly cloudy") <= 1
    assert "Pennsylvania, United States of America" not in text
    assert "team lookup matched" not in text
