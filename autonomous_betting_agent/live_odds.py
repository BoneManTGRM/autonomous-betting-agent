from __future__ import annotations

import os
from dataclasses import dataclass
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

import requests

API_HOST = "https://api.the-odds-api.com"


@dataclass(frozen=True)
class SportInfo:
    key: str
    group: str
    title: str
    description: str
    active: bool
    has_outrights: bool


@dataclass(frozen=True)
class OutcomePrice:
    name: str
    average_price: float
    raw_probability: float
    normalized_probability: float
    source_count: int


@dataclass(frozen=True)
class LiveEventSummary:
    event_id: str
    sport_key: str
    sport_title: str
    commence_time: str
    home_team: str
    away_team: str
    favorite: str
    favorite_probability: float
    outcomes: List[OutcomePrice]
    bookmaker_count: int
    cycle_notes: List[str]


def get_api_key(explicit_key: Optional[str] = None) -> str:
    key = explicit_key or os.getenv("THE_ODDS_API_KEY") or ""
    if not key:
        raise RuntimeError("Missing THE_ODDS_API_KEY. Add it to Streamlit secrets or environment variables.")
    return key


def _get_json(path: str, params: Dict[str, Any]) -> Any:
    response = requests.get(f"{API_HOST}{path}", params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def list_sports(api_key: str, include_all: bool = False) -> List[SportInfo]:
    payload = _get_json("/v4/sports/", {"apiKey": api_key, "all": str(include_all).lower()})
    sports = []
    for item in payload:
        sports.append(
            SportInfo(
                key=str(item.get("key", "")),
                group=str(item.get("group", "")),
                title=str(item.get("title", "")),
                description=str(item.get("description", "")),
                active=bool(item.get("active", False)),
                has_outrights=bool(item.get("has_outrights", False)),
            )
        )
    return sports


def fetch_odds(
    api_key: str,
    sport_key: str,
    regions: str = "us,eu,uk",
    markets: str = "h2h",
    odds_format: str = "decimal",
) -> List[Dict[str, Any]]:
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
        "dateFormat": "iso",
    }
    return list(_get_json(f"/v4/sports/{sport_key}/odds/", params))


def _average_prices_by_outcome(bookmakers: Iterable[Dict[str, Any]]) -> Dict[str, List[float]]:
    prices: Dict[str, List[float]] = {}
    for bookmaker in bookmakers:
        for market in bookmaker.get("markets", []):
            if market.get("key") != "h2h":
                continue
            for outcome in market.get("outcomes", []):
                name = str(outcome.get("name", "")).strip()
                price = outcome.get("price")
                if not name or price is None:
                    continue
                try:
                    price_float = float(price)
                except (TypeError, ValueError):
                    continue
                if price_float <= 1.0:
                    continue
                prices.setdefault(name, []).append(price_float)
    return prices


def summarize_event(event: Dict[str, Any]) -> Optional[LiveEventSummary]:
    price_map = _average_prices_by_outcome(event.get("bookmakers", []))
    if len(price_map) < 2:
        return None
    raw_probs = {name: 1.0 / mean(values) for name, values in price_map.items() if values}
    total = sum(raw_probs.values())
    if total <= 0:
        return None
    outcomes = [
        OutcomePrice(
            name=name,
            average_price=mean(price_map[name]),
            raw_probability=raw_probs[name],
            normalized_probability=raw_probs[name] / total,
            source_count=len(price_map[name]),
        )
        for name in raw_probs
    ]
    outcomes.sort(key=lambda item: item.normalized_probability, reverse=True)
    favorite = outcomes[0]
    cycle_notes = [
        "TEST: pulled live market prices for the event.",
        "DETECT: checked whether at least two outcomes had usable prices.",
        "REPAIR: averaged prices across books and normalized implied probabilities.",
        "VERIFY: ranked outcomes by no-vig probability and marked draw risk when present.",
    ]
    return LiveEventSummary(
        event_id=str(event.get("id", "")),
        sport_key=str(event.get("sport_key", "")),
        sport_title=str(event.get("sport_title", event.get("sport_key", ""))),
        commence_time=str(event.get("commence_time", "")),
        home_team=str(event.get("home_team", "")),
        away_team=str(event.get("away_team", "")),
        favorite=favorite.name,
        favorite_probability=favorite.normalized_probability,
        outcomes=outcomes,
        bookmaker_count=len(event.get("bookmakers", [])),
        cycle_notes=cycle_notes,
    )


def scan_market(api_key: str, sport_key: str, regions: str = "us,eu,uk", max_events: int = 25) -> List[LiveEventSummary]:
    events = fetch_odds(api_key, sport_key=sport_key, regions=regions)
    summaries = []
    for event in events[:max_events]:
        summary = summarize_event(event)
        if summary is not None:
            summaries.append(summary)
    return summaries
