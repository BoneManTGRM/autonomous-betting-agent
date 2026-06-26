from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "autonomous_betting_agent" / "magazine_book_export.py"
SPEC = importlib.util.spec_from_file_location("magazine_book_export_base_api", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
magazine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(magazine)


def _clear_api_env(monkeypatch):
    for names in magazine.API_SECRET_DEFS.values():
        for name in names:
            monkeypatch.delenv(name, raising=False)


def _row() -> dict[str, str]:
    return {
        "event_name": "Iraq vs France",
        "away_team": "Iraq",
        "home_team": "France",
        "sport": "FIFA WORLD CUP",
        "pick": "OVER 2.5",
        "decimal_price": "1.36",
        "odds_source": "The Odds API",
        "bookmaker": "consensus average",
        "risk": "VOLUME OK",
    }


def test_base_renderer_detects_configured_non_odds_apis(monkeypatch):
    _clear_api_env(monkeypatch)
    monkeypatch.setenv("SPORTSDATAIO_API_KEY", "configured")
    monkeypatch.setenv("WEATHERAPI_KEY", "configured")
    monkeypatch.setenv("API_FOOTBALL_KEY", "configured")
    monkeypatch.setenv("NEWSAPI_KEY", "configured")
    row = _row()
    provenance = magazine.api_provenance(row)
    assert provenance["active_sources"] == ["SportsDataIO", "WeatherAPI", "API-Football", "NewsAPI"]
    assert "Odds API" in provenance["inactive_sources"]
    assert "Perplexity" in provenance["inactive_sources"]
    assert magazine._odds_row_label(row) == "uploaded/cached row"


def test_base_renderer_pairs_show_active_apis_instead_of_source_odds_api(monkeypatch):
    _clear_api_env(monkeypatch)
    monkeypatch.setenv("SPORTSDATAIO_API_KEY", "configured")
    monkeypatch.setenv("WEATHERAPI_KEY", "configured")
    monkeypatch.setenv("API_FOOTBALL_KEY", "configured")
    monkeypatch.setenv("NEWSAPI_KEY", "configured")
    pairs = magazine._pairs(_row(), "en")
    assert ("ODDS ROW", "uploaded/cached row") in pairs
    pair_text = "\n".join(f"{k}: {v}" for k, v in pairs)
    assert "ACTIVE APIS: SportsDataIO · WeatherAPI · API-Football · NewsAPI" in pair_text
    assert "SOURCE: The Odds API" not in pair_text


def test_base_renderer_fallbacks_mention_active_apis(monkeypatch):
    _clear_api_env(monkeypatch)
    monkeypatch.setenv("SPORTSDATAIO_API_KEY", "configured")
    monkeypatch.setenv("WEATHERAPI_KEY", "configured")
    monkeypatch.setenv("API_FOOTBALL_KEY", "configured")
    monkeypatch.setenv("NEWSAPI_KEY", "configured")
    row = _row()
    assert any("Active APIs checked: SportsDataIO · WeatherAPI · API-Football · NewsAPI." in item for item in magazine._team_items(row, "away"))
    assert any("Active APIs checked: SportsDataIO · WeatherAPI · API-Football · NewsAPI." in item for item in magazine._injury_items(row, "home"))
    assert any("Active APIs checked: SportsDataIO · WeatherAPI · API-Football · NewsAPI." in item for item in magazine._matchup_items(row))
