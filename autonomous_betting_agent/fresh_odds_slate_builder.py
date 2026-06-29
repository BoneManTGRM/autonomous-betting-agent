from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd

SLATE_READY = "SLATE_READY"
SLATE_MISSING_FIELDS = "SLATE_MISSING_FIELDS"
SLATE_EMPTY = "SLATE_EMPTY"
SLATE_INVALID_PAYLOAD = "SLATE_INVALID_PAYLOAD"

SLATE_BUILDER_COLUMNS = [
    "slate_builder_source",
    "slate_builder_generated_at",
    "slate_builder_api_name",
    "slate_builder_sport",
    "slate_builder_market",
    "slate_builder_bookmaker",
    "slate_builder_event_start",
    "slate_builder_price_available",
    "slate_builder_ready_for_advisory_pipeline",
    "slate_builder_missing_fields",
    "slate_builder_safety_notes",
]

ADVISORY_COMPATIBLE_FIELDS = [
    "event",
    "prediction",
    "market_type",
    "bookmaker",
    "decimal_odds",
    "event_start_utc",
]

THE_ODDS_API_BASE_URL = "https://api.the-odds-api.com/v4/sports"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _records(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame | None) -> list[dict[str, Any]]:
    if rows_or_frame is None:
        return []
    if isinstance(rows_or_frame, pd.DataFrame):
        return rows_or_frame.to_dict("records")
    return [deepcopy(dict(row)) for row in rows_or_frame if isinstance(row, Mapping)]


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"none", "nan", "null", "nat", ""} else text


def _float(value: Any) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = float(text.replace(",", ""))
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _list_payload(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping) and isinstance(payload.get("data"), list):
        return [item for item in payload["data"] if isinstance(item, Mapping)]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)]
    return []


def _event_name(event: Mapping[str, Any]) -> str:
    home = _text(event.get("home_team"))
    away = _text(event.get("away_team"))
    title = _text(event.get("title") or event.get("name"))
    if home and away:
        return f"{away} vs {home}"
    return title or _text(event.get("id")) or "Unknown Event"


def _bookmaker_name(bookmaker: Mapping[str, Any]) -> str:
    return _text(bookmaker.get("title")) or _text(bookmaker.get("key")) or "unknown_bookmaker"


def _missing_fields(row: Mapping[str, Any]) -> list[str]:
    missing = []
    for field in ADVISORY_COMPATIBLE_FIELDS:
        value = row.get(field)
        if field == "decimal_odds":
            if _float(value) is None:
                missing.append(field)
        elif not _text(value):
            missing.append(field)
    return missing


def slate_builder_diagnostics(row: Mapping[str, Any]) -> dict[str, Any]:
    missing = _missing_fields(row)
    price_available = _float(row.get("decimal_odds")) is not None
    ready = not missing
    return {
        "slate_builder_price_available": bool(price_available),
        "slate_builder_ready_for_advisory_pipeline": bool(ready),
        "slate_builder_missing_fields": ",".join(missing),
        "slate_builder_safety_notes": "Streamlit/session-only slate row. No server, no database, no scheduler, no background polling, no persistent cache, no key exposure, no live betting, no proof mutation, no result mutation, and no bankroll action.",
    }


def normalize_the_odds_api_events(
    payload: Any,
    *,
    sport: str = "",
    market: str = "",
    bookmaker_filter: str = "",
    generated_at: str | None = None,
) -> list[dict[str, Any]]:
    generated = generated_at or utc_now_iso()
    rows: list[dict[str, Any]] = []
    wanted_book = bookmaker_filter.strip().lower()
    for event in _list_payload(payload):
        event_name = _event_name(event)
        sport_key = _text(sport or event.get("sport_key") or event.get("sport_title"))
        start_time = _text(event.get("commence_time") or event.get("event_start_utc") or event.get("start_time"))
        for bookmaker in event.get("bookmakers", []) or []:
            if not isinstance(bookmaker, Mapping):
                continue
            book_key = _text(bookmaker.get("key"))
            book_title = _bookmaker_name(bookmaker)
            if wanted_book and wanted_book not in {book_key.lower(), book_title.lower()}:
                continue
            last_update = _text(bookmaker.get("last_update"))
            for market_payload in bookmaker.get("markets", []) or []:
                if not isinstance(market_payload, Mapping):
                    continue
                market_key = _text(market_payload.get("key") or market)
                if market and market_key and market_key.lower() != market.lower():
                    continue
                for outcome in market_payload.get("outcomes", []) or []:
                    if not isinstance(outcome, Mapping):
                        continue
                    price = _float(outcome.get("price"))
                    row: dict[str, Any] = {
                        "event": event_name,
                        "event_id": _text(event.get("id")),
                        "sport": sport_key,
                        "league": _text(event.get("sport_title")),
                        "prediction": _text(outcome.get("name")),
                        "selection": _text(outcome.get("name")),
                        "market_type": market_key,
                        "market": market_key,
                        "bookmaker": book_title,
                        "sportsbook": book_title,
                        "bookmaker_key": book_key,
                        "decimal_odds": price,
                        "event_start_utc": start_time,
                        "odds_timestamp": last_update,
                        "line": outcome.get("point"),
                        "slate_builder_source": "streamlit_user_triggered_api_or_upload",
                        "slate_builder_generated_at": generated,
                        "slate_builder_api_name": "The Odds API",
                        "slate_builder_sport": sport_key,
                        "slate_builder_market": market_key,
                        "slate_builder_bookmaker": book_title,
                        "slate_builder_event_start": start_time,
                    }
                    row.update(slate_builder_diagnostics(row))
                    rows.append(row)
    return rows


def normalize_sportsdataio_events(payload: Any, *, sport: str = "", generated_at: str | None = None) -> list[dict[str, Any]]:
    generated = generated_at or utc_now_iso()
    rows: list[dict[str, Any]] = []
    for event in _list_payload(payload):
        home = _text(event.get("HomeTeam") or event.get("HomeTeamName") or event.get("home_team"))
        away = _text(event.get("AwayTeam") or event.get("AwayTeamName") or event.get("away_team"))
        event_name = f"{away} vs {home}" if home and away else _text(event.get("Name") or event.get("GameID") or event.get("id")) or "Unknown Event"
        start_time = _text(event.get("DateTimeUTC") or event.get("DateTime") or event.get("Day") or event.get("start_time"))
        base = {
            "event": event_name,
            "event_id": _text(event.get("GameID") or event.get("id")),
            "sport": _text(sport or event.get("Sport") or event.get("sport")),
            "league": _text(event.get("League") or event.get("Competition")),
            "event_start_utc": start_time,
            "slate_builder_source": "streamlit_user_triggered_api_or_upload",
            "slate_builder_generated_at": generated,
            "slate_builder_api_name": "SportsDataIO",
            "slate_builder_sport": _text(sport or event.get("Sport") or event.get("sport")),
            "slate_builder_event_start": start_time,
            "slate_builder_market": "event_context",
            "slate_builder_bookmaker": "context_only",
        }
        row = {
            **base,
            "prediction": _text(event.get("HomeTeam") or event.get("HomeTeamName") or home),
            "selection": _text(event.get("HomeTeam") or event.get("HomeTeamName") or home),
            "market_type": "event_context",
            "market": "event_context",
            "bookmaker": "context_only",
            "sportsbook": "context_only",
            "decimal_odds": None,
        }
        row.update(slate_builder_diagnostics(row))
        rows.append(row)
    return rows


def build_slate_rows_from_payload(api_name: str, payload: Any, **kwargs: Any) -> list[dict[str, Any]]:
    name = api_name.strip().lower()
    if name in {"the odds api", "odds", "the_odds_api"}:
        return normalize_the_odds_api_events(payload, **kwargs)
    if name in {"sportsdataio", "sportsdata", "sportsdata.io"}:
        return normalize_sportsdataio_events(payload, sport=str(kwargs.get("sport", "")))
    return []


def fetch_the_odds_api_payload(
    api_key: str,
    *,
    sport_key: str,
    regions: str = "us",
    markets: str = "h2h",
    odds_format: str = "decimal",
    bookmakers: str = "",
    timeout: int = 15,
    requester: Callable[[str, int], str] | None = None,
) -> Any:
    if not _text(api_key):
        raise ValueError("missing_api_key")
    if not _text(sport_key):
        raise ValueError("missing_sport_key")
    params = {
        "apiKey": api_key,
        "regions": regions,
        "markets": markets,
        "oddsFormat": odds_format,
    }
    if _text(bookmakers):
        params["bookmakers"] = bookmakers
    url = f"{THE_ODDS_API_BASE_URL}/{sport_key}/odds?{urlencode(params)}"
    if requester is None:
        with urlopen(url, timeout=timeout) as response:  # noqa: S310 - user-triggered API request only.
            data = response.read().decode("utf-8")
    else:
        data = requester(url, timeout)
    return json.loads(data)


def slate_builder_summary(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame | None) -> pd.DataFrame:
    rows = _records(rows_or_frame)
    if not rows:
        return pd.DataFrame(columns=["slate_builder_status", "row_count", "ready_rows", "missing_field_rows", "price_available_rows"])
    frame = pd.DataFrame(rows)
    ready = frame.get("slate_builder_ready_for_advisory_pipeline", pd.Series(dtype=bool)).fillna(False).astype(bool)
    price = frame.get("slate_builder_price_available", pd.Series(dtype=bool)).fillna(False).astype(bool)
    missing = frame.get("slate_builder_missing_fields", pd.Series(dtype=str)).fillna("").astype(str) != ""
    status = SLATE_READY if bool(ready.any()) else SLATE_MISSING_FIELDS
    return pd.DataFrame([{
        "slate_builder_status": status,
        "row_count": int(len(frame)),
        "ready_rows": int(ready.sum()),
        "missing_field_rows": int(missing.sum()),
        "price_available_rows": int(price.sum()),
    }])


def slate_builder_report_section(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame | None) -> str:
    rows = _records(rows_or_frame)
    if not rows:
        return "Fresh Odds Slate Builder\n- No slate rows available."
    summary = slate_builder_summary(rows).iloc[0].to_dict()
    return "\n".join([
        "Fresh Odds Slate Builder",
        "- Streamlit/session-only, user-triggered slate building.",
        f"- Rows: {summary.get('row_count')}; ready rows: {summary.get('ready_rows')}; missing-field rows: {summary.get('missing_field_rows')}.",
        f"- Price-available rows: {summary.get('price_available_rows')}.",
        "- Safety: no server, no database, no scheduled polling, no persistent cache, no key exposure, no proof mutation, no result mutation, no live betting, no bankroll action.",
    ])


def redact_api_key_from_text(value: str, api_key: str) -> str:
    if not api_key:
        return value
    return value.replace(api_key, "[REDACTED_API_KEY]")
