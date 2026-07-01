from __future__ import annotations

from typing import Any
import re

PATCH_VERSION = "magazine_readability_v1"


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _first(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        text = _clean(data.get(key))
        if text and text.lower() not in {"nan", "none", "null", "n/a", "na", "--", "data unavailable"}:
            return text
    return default


def _short(text: str, limit: int = 132) -> str:
    text = _clean(text)
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" .,;:") + "."


def compact_context_rows(row: dict[str, Any]) -> list[str]:
    rows: list[str] = []
    weather = _first(row, "weather_summary_short", "weather_summary", "venue_weather", "weather_risk")
    context = _first(row, "expanded_matchup_context", "sports_context_summary", "preview_summary", "game_summary", "matchup_note", "matchup_notes")
    news = _first(row, "news_summary", "newsapi_summary", "perplexity_summary", "perplexity_context", "api_football_summary", "sportsdataio_context")
    line = _first(row, "line_movement_summary", "line_movement", "price_movement", default="Line movement: verify current market before entry.")
    if weather:
        rows.append("Weather: " + _short(weather, 118))
    if context:
        rows.append("Context: " + _short(context, 128))
    if news and news != context:
        rows.append("News: " + _short(news, 118))
    rows.append(_short(line, 118))
    return rows[:4]


def install() -> bool:
    try:
        from autonomous_betting_agent import magazine_sale_ready_patch as sale
    except Exception:
        return False
    sale._expanded_context_rows = compact_context_rows
    sale._ABA_MATCHUP_NOTES_READABILITY_PATCH = PATCH_VERSION
    return True
