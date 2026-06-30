from __future__ import annotations

import builtins
import hashlib
import importlib
import json
import os
import re
import time
from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote_plus, urlencode
from urllib.request import Request, urlopen

ENRICHMENT_VERSION = "live_api_enrichment_v13_truth_compatible"
_TIMEOUT_SECONDS = 7.0
_CACHE: dict[tuple[str, str], Any] = {}
_RUN_COUNTER = 0
_SPANISH_TR_MARKER = "_aba_spanish_report_tr_v13"
_RELOAD_MARKER = "_aba_magazine_reload_patch_v13"

API_SECRET_DEFS = {
    "Odds API": ("ODDS_API_KEY", "THE_ODDS_API_KEY"),
    "SportsDataIO": ("SPORTSDATAIO_API_KEY", "SPORTS_DATA_IO_API_KEY", "SPORTSDATA_API_KEY"),
    "WeatherAPI": ("WEATHERAPI_KEY", "WEATHER_API_KEY"),
    "API-Football": ("API_FOOTBALL_KEY", "APIFOOTBALL_KEY"),
    "NewsAPI": ("NEWSAPI_KEY", "NEWS_API_KEY"),
    "Perplexity": ("PERPLEXITY_API_KEY", "PPLX_API_KEY"),
}

FALLBACK_TOKENS = (
    "context unavailable",
    "no sdio event id",
    "sdio checked; no provider event id",
    "api-fb lookup checked",
    "api-fb team lookup checked",
    "no fixture match",
    "no match returned",
    "show hn: simple news aggregator",
    "simple news aggregator",
    "uploaded/cached row",
    "fila cargada/en caché",
    "no live",
    "data not returned for this event",
    "player data not returned for this event",
    "datos no disponibles para este evento",
    "datos de jugadores no disponibles para este evento",
    "api key missing",
    "payment required",
)


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return dict(data) if isinstance(data, Mapping) else {}
    return dict(getattr(value, "__dict__", {}) or {})


def _bad(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _useful(value: Any) -> bool:
    if _bad(value):
        return False
    text = str(value).strip().lower()
    if text in {"false", "0", "no", "not available", "unavailable", "data unavailable", "none available"}:
        return False
    return not any(token in text for token in FALLBACK_TOKENS)


def _get(row: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = row.get(key)
        if not _bad(value):
            return str(value).strip()
    return default


def _secret(*names: str) -> str:
    getter = getattr(builtins, "get_secret", None)
    if callable(getter):
        try:
            value = str(getter(*names) or "").strip()
            if value:
                return value
        except Exception:
            pass
    try:
        import streamlit as st  # type: ignore
        for name in names:
            try:
                value = str(st.secrets.get(name, "") or "").strip()
            except Exception:
                value = ""
            if value:
                return value
    except Exception:
        pass
    for name in names:
        value = str(os.getenv(name, "") or "").strip()
        if value:
            return value
    return ""


def _mask(value: str) -> str:
    text = str(value or "")
    if not text:
        return ""
    return "***" if len(text) <= 8 else f"{text[:4]}...{text[-4:]}"


def check_api_health(mask_secrets: bool = True) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for name, keys in API_SECRET_DEFS.items():
        key = _secret(*keys)
        out[name] = {
            "status": "CONFIGURED" if key else "API_KEY_MISSING",
            "key": _mask(key) if mask_secrets and key else ("present" if key else ""),
        }
    return out


def _is_spanish(row: Mapping[str, Any]) -> bool:
    text = _get(row, "report_language", "language", "lang").lower()
    return text.startswith("es") or "español" in text or "espanol" in text or "spanish" in text


def _sport_kind(row: Mapping[str, Any]) -> str:
    text = " ".join(str(row.get(key, "")) for key in ("sport", "league", "event", "game", "matchup", "event_name")).lower()
    if any(token in text for token in ("mma", "ufc", "boxing", "fighter")):
        return "combat"
    if any(token in text for token in ("soccer", "fifa", "football", "world cup", "uefa", "liga")):
        return "soccer"
    if any(token in text for token in ("mlb", "baseball")):
        return "baseball"
    return "generic"


def _split_teams(row: Mapping[str, Any]) -> tuple[str, str]:
    away = _get(row, "away_team", "team_a", "team1")
    home = _get(row, "home_team", "team_b", "team2")
    if away and home:
        return away, home
    event = _get(row, "public_event", "event", "game", "event_name", "matchup")
    for sep in (" at ", " vs ", " VS ", " v ", " @ "):
        if sep in event:
            left, right = event.split(sep, 1)
            return left.strip(), right.strip()
    return _get(row, "team", default=""), _get(row, "opponent", default="")


def _normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\s+(?:at|vs|v|@)\s+", " vs ", text)
    text = re.sub(r"[^a-z0-9áéíóúüñ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _event_key(row: Mapping[str, Any]) -> str:
    away, home = _split_teams(row)
    event = _get(row, "public_event", "event", "game", "event_name", "matchup") or f"{away} vs {home}".strip()
    return "|".join(
        part for part in (
            _normalize_text(event),
            _normalize_text(_get(row, "sport", "league")),
            _get(row, "event_date", "event_start_utc", "start_time", "commence_time")[:10],
        ) if part
    ) or "unknown_event"


def _hash_payload(value: Any) -> str:
    try:
        text = json.dumps(value, sort_keys=True, default=str, ensure_ascii=False)
    except Exception:
        text = str(value)
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _new_run_meta(rows: list[Any] | tuple[Any, ...]) -> tuple[str, str]:
    global _RUN_COUNTER
    _RUN_COUNTER += 1
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"aba_mag_{int(time.time())}_{_RUN_COUNTER}_{_hash_payload(rows)}", ts


def _set_if_empty(row: dict[str, Any], key: str, value: str) -> None:
    if value and not _useful(row.get(key)):
        row[key] = value


def _request_json(url: str, *, headers: Mapping[str, str] | None = None, cache_key: tuple[str, str] | None = None, timeout: float = _TIMEOUT_SECONDS) -> Any:
    key = cache_key or ("url", url)
    if key in _CACHE:
        return _CACHE[key]
    req = Request(url, headers={"User-Agent": "ABA-Signal-Pro/1.0", **dict(headers or {})})
    try:
        with urlopen(req, timeout=timeout) as response:  # noqa: S310 - controlled API URLs only
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        data = {"_error": exc.__class__.__name__}
    _CACHE[key] = data
    return data


def _request_post_json(url: str, payload: Mapping[str, Any], *, headers: Mapping[str, str] | None = None, cache_key: tuple[str, str] | None = None, timeout: float = _TIMEOUT_SECONDS) -> Any:
    key = cache_key or ("post", url + _hash_payload(payload))
    if key in _CACHE:
        return _CACHE[key]
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        method="POST",
        headers={"User-Agent": "ABA-Signal-Pro/1.0", "Content-Type": "application/json", **dict(headers or {})},
    )
    try:
        with urlopen(req, timeout=timeout) as response:  # noqa: S310 - controlled API URL only
            data = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        data = {"_error": exc.__class__.__name__}
    _CACHE[key] = data
    return data


def _candidate_location(row: Mapping[str, Any]) -> str:
    explicit = _get(row, "weather_location", "venue_weather_location", "venue", "event_location", "location", "city")
    if explicit:
        return explicit
    joined = " | ".join(str(row.get(key, "")) for key in ("venue_note", "matchup_note", "matchup_notes", "sports_context_summary", "weather_summary", "event", "event_name"))
    patterns = (
        r"([A-Z][A-Za-z .'-]+,\s*[A-Z][A-Za-z .'-]+,\s*(?:USA|United States|United States of America|Mexico|Canada))",
        r"([A-Z][A-Za-z .'-]+,\s*(?:USA|United States|United States of America|Mexico|Canada))",
    )
    for pattern in patterns:
        match = re.search(pattern, joined)
        if match:
            return match.group(1).strip(" .")
    return ""


def _enrich_weather(row: dict[str, Any]) -> None:
    key = _secret(*API_SECRET_DEFS["WeatherAPI"])
    if not key:
        row.setdefault("weather_status", "API_KEY_MISSING")
        row.setdefault("weather_failure_reason", "WeatherAPI key missing")
        return
    spanish = _is_spanish(row)
    location = _candidate_location(row)
    if not location:
        row["weather_status"] = "NO_LOCATION"
        row["weather_failure_reason"] = "No venue/location in row"
        _set_if_empty(row, "weather_summary", "Clima revisado; no hay sede/ubicación en la fila." if spanish else "Weather checked; no venue/location in row.")
        return
    url = "https://api.weatherapi.com/v1/current.json?" + urlencode({"key": key, "q": location, "aqi": "no"})
    data = _request_json(url, cache_key=("weather", location.lower()))
    current = data.get("current") if isinstance(data, Mapping) else None
    place = data.get("location") if isinstance(data, Mapping) else None
    if not isinstance(current, Mapping):
        row["weather_status"] = "API_ERROR" if isinstance(data, Mapping) and data.get("_error") else "NO_LIVE_PAYLOAD"
        row["weather_failure_reason"] = str(data.get("_error") if isinstance(data, Mapping) else "No live weather payload")
        _set_if_empty(row, "weather_summary", f"Clima revisado: {location}; sin datos en vivo." if spanish else f"Weather checked: {location}; no live payload.")
        return
    condition = current.get("condition") if isinstance(current.get("condition"), Mapping) else {}
    condition_text = str(condition.get("text", "conditions available"))
    if spanish:
        condition_text = {"sunny": "soleado", "clear": "despejado", "cloudy": "nublado", "partly cloudy": "parcialmente nublado"}.get(condition_text.lower(), condition_text)
        weather = f"Clima: {condition_text}, {current.get('temp_c')}°C, viento {current.get('wind_kph')} kph."
    else:
        weather = f"Weather: {condition_text}, {current.get('temp_c')}°C, wind {current.get('wind_kph')} kph."
    place_name = ", ".join(str(place.get(k)) for k in ("name", "region", "country") if isinstance(place, Mapping) and place.get(k))
    summary = weather + ((f" Ubicación: {place_name}." if spanish else f" Location: {place_name}.") if place_name else "")
    row["weather_status"] = "LIVE"
    _set_if_empty(row, "weather_summary", summary)
    _set_if_empty(row, "venue_weather", summary)


def _news_query(row: Mapping[str, Any]) -> str:
    away, home = _split_teams(row)
    event = _get(row, "event", "game", "event_name", "matchup")
    base = f"{away} {home}".strip() or event
    terms = " injury camp news" if _sport_kind(row) == "combat" else " injury lineup news odds"
    return (base + terms).strip()


def _enrich_news(row: dict[str, Any]) -> None:
    key = _secret(*API_SECRET_DEFS["NewsAPI"])
    if not key:
        row.setdefault("news_status", "API_KEY_MISSING")
        row.setdefault("news_failure_reason", "NewsAPI key missing")
        return
    spanish = _is_spanish(row)
    query = _news_query(row)
    if not query:
        row["news_status"] = "NO_QUERY"
        row["news_failure_reason"] = "No event/team query available"
        return
    params = {"apiKey": key, "q": query, "language": "en", "sortBy": "publishedAt", "pageSize": "3"}
    data = _request_json("https://newsapi.org/v2/everything?" + urlencode(params), cache_key=("news", query.lower()))
    articles = data.get("articles") if isinstance(data, Mapping) else None
    if not isinstance(articles, list) or not articles:
        row["news_status"] = "NO_RECENT_MATCHES"
        row["news_failure_reason"] = "No recent matching articles returned"
        _set_if_empty(row, "newsapi_summary", "Noticias revisadas; sin artículos recientes relacionados." if spanish else "News checked; no recent matching articles.")
        _set_if_empty(row, "news_summary", row.get("newsapi_summary", ""))
        _set_if_empty(row, "news_injury_summary", "Noticias revisadas; sin titular de lesiones/alineación." if spanish else "News checked; no injury/lineup headline.")
        return
    titles = [str(item.get("title", "")).strip() for item in articles if isinstance(item, Mapping) and item.get("title")]
    titles = [title for title in titles if title][:3]
    if not titles:
        row["news_status"] = "NO_TITLE"
        row["news_failure_reason"] = "Articles returned without usable titles"
        return
    first = titles[0][:88].rstrip() + ("…" if len(titles[0]) > 88 else "")
    row["news_status"] = "LIVE"
    _set_if_empty(row, "newsapi_summary", ("Noticias: " if spanish else "News: ") + first)
    _set_if_empty(row, "news_summary", row.get("newsapi_summary", ""))
    _set_if_empty(row, "news_injury_summary", ("Noticias: " if spanish else "News: ") + first)


def _api_football_team_search(team: str, key: str) -> str:
    if not team:
        return ""
    url = "https://v3.football.api-sports.io/teams?search=" + quote_plus(team)
    data = _request_json(url, headers={"x-apisports-key": key}, cache_key=("api-football-team", team.lower()))
    response = data.get("response") if isinstance(data, Mapping) else None
    if not isinstance(response, list) or not response:
        return ""
    item = response[0]
    team_data = item.get("team") if isinstance(item, Mapping) else None
    if not isinstance(team_data, Mapping):
        return ""
    return str(team_data.get("name") or team)


def _enrich_api_football(row: dict[str, Any]) -> None:
    if _sport_kind(row) != "soccer":
        row.setdefault("api_football_match_status", "SPORT_UNSUPPORTED")
        row.setdefault("api_football_failure_reason", "Not a soccer/FIFA row")
        return
    key = _secret(*API_SECRET_DEFS["API-Football"])
    if not key:
        row.setdefault("api_football_match_status", "API_KEY_MISSING")
        row.setdefault("api_football_failure_reason", "API-Football key missing")
        return
    spanish = _is_spanish(row)
    away, home = _split_teams(row)
    away_result = _api_football_team_search(away, key)
    home_result = _api_football_team_search(home, key)
    if away_result or home_result:
        matched = " / ".join(part for part in (away_result or away, home_result or home) if part)
        summary = f"API-FB encontró equipos {matched}; partido no verificado." if spanish else f"API-FB team lookup matched {matched}; fixture not verified."
        row["api_football_match_status"] = "TEAM_MATCHED_FIXTURE_UNVERIFIED"
    else:
        summary = "API-FB: búsqueda revisada; sin coincidencia de partido." if spanish else f"API-FB team lookup checked {away or 'away'} / {home or 'home'}; no match returned."
        row["api_football_match_status"] = "NO_MATCH_TEAM_NAME"
        row["api_football_failure_reason"] = "Team lookup returned no match"
    _set_if_empty(row, "api_football_team_summary", summary)
    _set_if_empty(row, "api_football_summary", summary)


def _enrich_sportsdataio(row: dict[str, Any]) -> None:
    if not _secret(*API_SECRET_DEFS["SportsDataIO"]):
        row.setdefault("sportsdataio_match_status", "API_KEY_MISSING")
        row.setdefault("sportsdataio_failure_reason", "SportsDataIO key missing")
        return
    existing = _get(row, "sportsdataio_team_summary", "sportsdataio_context", "sportsdataio_injury_summary", "sportsdataio_game_summary")
    if existing:
        row["sportsdataio_match_status"] = "ROW_ALREADY_HAS_CONTEXT"
        return
    row["sportsdataio_match_status"] = "NO_PROVIDER_EVENT_ID"
    row["sportsdataio_failure_reason"] = "No provider event ID in row"
    summary = "SDIO revisado; sin ID de evento del proveedor." if _is_spanish(row) else "SDIO checked; no provider event ID in row."
    _set_if_empty(row, "sportsdataio_context", summary)
    _set_if_empty(row, "sportsdataio_team_summary", summary)


def _enrich_perplexity(row: dict[str, Any]) -> None:
    existing = _get(row, "perplexity_context", "perplexity_summary", "pplx_context", "pplx_summary")
    if _useful(existing):
        row["perplexity_status"] = "LIVE"
        row["perplexity_context"] = existing
        return
    key = _secret(*API_SECRET_DEFS["Perplexity"])
    if not key:
        row["perplexity_status"] = "API_KEY_MISSING"
        row["perplexity_failure_reason"] = "Perplexity key missing"
        return
    event = _get(row, "public_event", "event", "event_name", "matchup", "game")
    pick = _get(row, "public_pick", "prediction", "pick", "selection", "recommended_action")
    if not event and not pick:
        row["perplexity_status"] = "NO_QUERY"
        row["perplexity_failure_reason"] = "No event/pick query available"
        return
    payload = {
        "model": "sonar",
        "messages": [
            {"role": "system", "content": "Write one concise sports research sentence. Do not invent unverified injury, lineup, or odds data."},
            {"role": "user", "content": f"Event: {event}. Pick: {pick}. Sport/league: {_get(row, 'sport', 'league')}. Give concise context only."},
        ],
        "max_tokens": 80,
        "temperature": 0.1,
    }
    data = _request_post_json(
        "https://api.perplexity.ai/chat/completions",
        payload,
        headers={"Authorization": f"Bearer {key}"},
        cache_key=("perplexity", _event_key(row)),
    )
    if isinstance(data, Mapping) and data.get("_error"):
        row["perplexity_status"] = "API_ERROR"
        row["perplexity_failure_reason"] = str(data.get("_error"))
        return
    content = ""
    choices = data.get("choices") if isinstance(data, Mapping) else None
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") if isinstance(choices[0], Mapping) else None
        if isinstance(msg, Mapping):
            content = str(msg.get("content") or "").strip()
    if _useful(content):
        row["perplexity_status"] = "LIVE"
        row["perplexity_context"] = re.sub(r"\s+", " ", content).strip()[:260]
    else:
        row["perplexity_status"] = "NO_LIVE_CONTEXT_RETURNED"
        row["perplexity_failure_reason"] = "Perplexity returned no usable context for this row"


def _safe_float(value: Any) -> float | None:
    if _bad(value):
        return None
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except Exception:
        return None


def _fmt_pct(value: Any, signed: bool = False) -> str:
    parsed = _safe_float(value)
    if parsed is None:
        return ""
    parsed = parsed / 100 if abs(parsed) > 1 else parsed
    return f"{parsed:+.1%}" if signed else f"{parsed:.0%}"


def _fmt_ev(value: Any) -> str:
    parsed = _safe_float(value)
    return "" if parsed is None else f"{parsed:+.3f}"


def _probability(row: Mapping[str, Any]) -> tuple[float | None, str]:
    for key in ("learned_model_probability", "model_probability_clean", "model_probability", "final_probability", "probability", "confidence"):
        value = _safe_float(row.get(key))
        if value is not None:
            value = value / 100 if abs(value) > 1 else value
            if 0 <= value <= 1:
                return value, key
    return None, "MISSING"


def _decimal_odds(row: Mapping[str, Any]) -> tuple[float | None, str]:
    for key in ("decimal_odds", "decimal_price", "best_price", "average_price", "avg_price", "odds_decimal", "odds_at_pick"):
        value = _safe_float(row.get(key))
        if value is not None and value > 1:
            return value, key
    american = _safe_float(row.get("american_odds") or row.get("odds_american") or row.get("odds"))
    if american is not None and abs(american) >= 100:
        decimal = (american / 100 + 1) if american > 0 else (100 / abs(american) + 1)
        return decimal, "american_odds"
    return None, "MISSING"


def _american_from_decimal(decimal: float | None) -> str:
    if decimal is None:
        return ""
    if decimal >= 2:
        return f"+{round((decimal - 1) * 100):.0f}"
    return f"-{round(100 / max(decimal - 1, 0.001)):.0f}"


def resolve_magazine_context(row: Mapping[str, Any]) -> tuple[str, str]:
    for source, key in (
        ("Perplexity", "perplexity_context"),
        ("Perplexity", "perplexity_summary"),
        ("NewsAPI", "newsapi_summary"),
        ("NewsAPI", "news_summary"),
        ("API-Football", "api_football_summary"),
        ("SportsDataIO", "sportsdataio_context"),
        ("WeatherAPI", "weather_summary"),
        ("Input", "sports_context_summary"),
        ("Input", "preview_summary"),
        ("Input", "game_summary"),
        ("Input", "short_reason"),
    ):
        value = row.get(key)
        if _useful(value):
            return source, str(value).strip()
    reasons = [str(row.get(k)) for k in ("perplexity_failure_reason", "news_failure_reason", "api_football_failure_reason", "sportsdataio_failure_reason", "weather_failure_reason", "odds_failure_reason") if row.get(k)]
    reason = "; ".join(reasons[:3]) or "no live context returned by configured sources"
    return "EMPTY_WITH_REASON", f"Context unavailable because: {reason}."


def _apply_odds_truth(row: dict[str, Any], refresh_time: str) -> None:
    prob, prob_source = _probability(row)
    decimal, decimal_source = _decimal_odds(row)
    row["model_probability_source"] = row.get("model_probability_source") or prob_source
    row["confidence_source"] = row.get("confidence_source") or prob_source
    row["confidence_status"] = "LIVE_OR_INPUT" if prob is not None else "MISSING"
    if prob is not None:
        row["model_probability"] = prob

    live_marker = str(row.get("odds_status") or row.get("odds_source") or row.get("odds_api_status") or "").strip().lower()
    live_odds = live_marker in {"live", "live_api", "odds api", "the odds api", "live_source"}
    if not _secret(*API_SECRET_DEFS["Odds API"]):
        row.setdefault("odds_api_status", "API_KEY_MISSING")
    elif not live_odds:
        row.setdefault("odds_api_status", "CONFIGURED_NO_LIVE_MATCH")

    if decimal is None:
        row["odds_status"] = "MISSING"
        row["odds_source"] = "MISSING"
        row["odds_failure_reason"] = f"No usable decimal odds field found; checked {decimal_source}."
        row["ev_status"] = "UNVERIFIED_ODDS_MISSING"
        return

    row["decimal_odds"] = decimal
    row["decimal_price"] = decimal
    row["american_odds"] = row.get("american_odds") or row.get("odds_american") or _american_from_decimal(decimal)
    row["raw_implied_probability"] = 1 / decimal
    row["market_probability"] = 1 / decimal
    row["odds_status"] = "LIVE" if live_odds else "UPLOADED_ROW"
    row["odds_source"] = "LIVE_API" if live_odds else "UPLOADED_ROW"
    if live_odds:
        row["odds_last_refresh"] = row.get("odds_last_refresh") or refresh_time
    else:
        row["odds_failure_reason"] = row.get("odds_failure_reason") or "No live Odds API match; using uploaded row price."

    if prob is not None:
        edge = prob - (1 / decimal)
        ev = prob * decimal - 1
        row["edge"] = edge
        row["model_market_edge"] = edge
        row["EV"] = ev
        row["expected_value_per_unit"] = ev
        row["fair_odds"] = 1 / prob if prob > 0 else ""
        row["ev_status"] = "RECALCULATED"
        row["ev_source"] = "LIVE" if live_odds else "FALLBACK_CALCULATED"
        row.setdefault("recommendation_status", "BET CANDIDATE" if ev > 0 else "WATCHLIST")
        row.setdefault("final_decision", "BET CANDIDATE" if ev > 0 else "WATCHLIST")
    else:
        row["ev_status"] = "UNVERIFIED_MODEL_PROBABILITY_MISSING"


def _ensure_required_report_fields(row: dict[str, Any], refresh_time: str) -> None:
    away, home = _split_teams(row)
    event_key = row.get("event_key") or _event_key(row)
    row["event_key"] = event_key
    row.setdefault("duplicate_group_id", event_key)
    row.setdefault("row_id", _hash_payload(row))
    row.setdefault("event_id", event_key)
    row.setdefault("sport", _get(row, "sport", "league", default="unknown"))
    row.setdefault("league", _get(row, "league", "sport", default="unknown"))
    event_time = _get(row, "event_date", "event_start_utc", "start_time", "commence_time", "start")
    row.setdefault("event_date", event_time[:10] if event_time else "")
    row.setdefault("start_time", event_time)
    row.setdefault("home_team", home)
    row.setdefault("away_team", away)
    row.setdefault("normalized_home_team", _normalize_text(home))
    row.setdefault("normalized_away_team", _normalize_text(away))
    row.setdefault("selected_market", _get(row, "selected_market", "market_type", "market", "public_market", default=""))
    row.setdefault("selected_pick", _get(row, "selected_pick", "public_pick", "prediction", "pick", "selection", default=""))
    row.setdefault("bookmaker", _get(row, "bookmaker", "book", default="consensus average"))
    row.setdefault("odds_last_refresh", "" if row.get("odds_status") != "LIVE" else refresh_time)
    row.setdefault("no_vig_implied_probability", "")
    row.setdefault("no_vig_edge", "")
    row.setdefault("no_vig_status", "UNAVAILABLE_MARKET_INCOMPLETE")
    row.setdefault("odds_market_sides_available", "false")
    row.setdefault("target_odds", "")
    row.setdefault("confidence_tier", _get(row, "confidence_tier", "confidence_bucket", "public_confidence", default=""))
    row.setdefault("units", _get(row, "units", "stake_units", "recommended_stake_units", default="0.1"))
    row.setdefault("risk_label", "FALLBACK MODE" if row.get("odds_status") != "LIVE" else "LIVE")
    row.setdefault("sportsdataio_event_id", _get(row, "sportsdataio_event_id", "sdio_event_id", default=""))
    row.setdefault("api_football_fixture_id", _get(row, "api_football_fixture_id", "fixture_id", default=""))
    row.setdefault("weather_summary", _get(row, "weather_summary", default=""))
    row.setdefault("news_summary", _get(row, "news_summary", "newsapi_summary", default=""))
    row.setdefault("perplexity_context", _get(row, "perplexity_context", "perplexity_summary", default=""))
    row.setdefault("injury_notes", _get(row, "injury_notes", "news_injury_summary", default="No lineup/injury headline returned."))
    row.setdefault("team_snapshot_home", _get(row, "team_snapshot_home", "sportsdataio_team_summary", "sportsdataio_context", default="No SDIO event ID."))
    row.setdefault("team_snapshot_away", _get(row, "team_snapshot_away", "sportsdataio_team_summary", "sportsdataio_context", default="No SDIO event ID."))
    row.setdefault("matchup_notes", _get(row, "matchup_notes", "sports_context_summary", default=""))
    row.setdefault("pro_bettor_evidence", _get(row, "pro_bettor_evidence", default=""))
    row.setdefault("reparodynamics_status", _get(row, "reparodynamics_status", default="OBSERVATION ONLY"))
    row.setdefault("reparodynamics_notes", _get(row, "reparodynamics_notes", default="Reparodynamics notes unavailable for this row."))
    row.setdefault("repair_flags", _get(row, "repair_flags", default=""))
    row.setdefault("weather_failure_reason", row.get("weather_failure_reason", ""))
    row.setdefault("news_failure_reason", row.get("news_failure_reason", ""))
    row.setdefault("perplexity_failure_reason", row.get("perplexity_failure_reason", ""))
    row.setdefault("sportsdataio_failure_reason", row.get("sportsdataio_failure_reason", ""))
    row.setdefault("api_football_failure_reason", row.get("api_football_failure_reason", ""))


def _apply_truth_fields(row: dict[str, Any], report_run_id: str, refresh_time: str) -> None:
    row["raw_input_hash"] = row.get("raw_input_hash") or _hash_payload({k: v for k, v in row.items() if not str(k).startswith("_")})
    row["enrichment_input_hash"] = row.get("enrichment_input_hash") or _hash_payload({"event_key": row.get("event_key") or _event_key(row), "api_health": check_api_health(True)})
    row["report_source"] = "final_enriched_picks_df"
    row["report_run_id"] = report_run_id
    row["last_api_refresh_time"] = refresh_time
    row["cache_status"] = row.get("cache_status") or "LIVE_REFRESH"
    row["data_freshness_status"] = row.get("data_freshness_status") or "CURRENT_REPORT_RUN"
    row["enrichment_status"] = row.get("enrichment_status") or "FINAL_ENRICHED"

    _apply_odds_truth(row, refresh_time)
    source, context = resolve_magazine_context(row)
    row["context_source"] = source
    row["context_status"] = "LIVE_OR_SOURCE_BACKED" if source != "EMPTY_WITH_REASON" else "EMPTY_WITH_REASON"
    if source == "EMPTY_WITH_REASON":
        row["context_failure_reason"] = context
    for key in ("sports_context_summary", "preview_summary", "game_summary", "short_reason", "matchup_notes"):
        _set_if_empty(row, key, context)

    fallback = row.get("odds_status") != "LIVE" or source == "EMPTY_WITH_REASON"
    row["fallback_used"] = str(bool(fallback))
    if fallback:
        parts = []
        if row.get("odds_status") != "LIVE":
            parts.append(f"odds_status={row.get('odds_status')}")
        if source == "EMPTY_WITH_REASON":
            parts.append("context_empty")
        row["fallback_reason"] = row.get("fallback_reason") or "; ".join(parts)
        row["risk_reasons"] = row.get("risk_reasons") or row.get("fallback_reason")
    else:
        row.setdefault("risk_reasons", "")

    _ensure_required_report_fields(row, refresh_time)
    row["field_provenance_json"] = json.dumps(
        {"report_source": "final_enriched_picks_df", "odds": row.get("odds_source"), "ev": row.get("ev_source") or row.get("ev_status"), "context": source},
        sort_keys=True,
    )
    row["source_trace_json"] = json.dumps(
        {"report_run_id": report_run_id, "event_key": row.get("event_key"), "fallback_used": row.get("fallback_used"), "fallback_reason": row.get("fallback_reason")},
        sort_keys=True,
    )
    row["api_health_json"] = json.dumps(check_api_health(True), sort_keys=True)
    row["api_sources_active"] = " · ".join([name for name, data in check_api_health(True).items() if data.get("status") == "CONFIGURED"])


def _spanish_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return text
    exact = {
        "PAGE": "PÁGINA", "OF": "DE", "WATCHLIST": "LISTA DE SEGUIMIENTO",
        "PLAY STANDARD": "JUGAR NORMAL", "PLAY SMALL": "JUGAR PEQUEÑO", "NO PLAY": "NO JUGAR",
        "BET CANDIDATE": "CANDIDATO A JUGAR",
        "uploaded/cached row": "fila cargada/en caché", "UPLOADED_ROW": "FILA CARGADA",
        "consensus average": "promedio consenso",
        "No lineup/injury headline returned.": "Sin titular de lesiones/alineación.",
        "API-FB: no fixture match.": "API-FB: sin coincidencia de partido.",
        "No SDIO event ID.": "Sin ID de evento SDIO.",
        "Price check required before entry.": "Revisar cuota antes de entrar.",
        "Context unavailable.": "Contexto no disponible.",
        "Data not returned for this event": "Datos no disponibles para este evento",
        "Player data not returned for this event": "Datos de jugadores no disponibles para este evento",
    }
    if text in exact:
        return exact[text]
    page_match = re.fullmatch(r"PAGE\s+(\d+)\s+OF\s+(\d+)", text, flags=re.I)
    if page_match:
        return f"PÁGINA {page_match.group(1)} DE {page_match.group(2)}"
    replacements = (
        (r"\bModel projects\b", "El modelo proyecta"),
        (r"\bprobability for\b", "de probabilidad para"),
        (r"\bMarket-implied probability checks at\b", "La probabilidad implícita del mercado es"),
        (r"\bMeasured edge\b", "Ventaja medida"),
        (r"\bExpected value\b", "Valor esperado"),
        (r"\bNegative edge at current price\b", "Ventaja negativa con la cuota actual"),
        (r"\bDo not play unless price improves\b", "No jugar salvo que la cuota mejore"),
        (r"\bRecheck odds and key news\b", "Revisar cuotas y noticias clave"),
        (r"\bDo not chain negative-EV picks\b", "No encadenar señales con VE negativo"),
        (r"\bAvoid parlays unless edge turns positive\b", "Evitar parlays salvo que la ventaja sea positiva"),
        (r"\bRecheck price before including\b", "Revisar la cuota antes de incluir"),
        (r"\bDo not play at the listed price\b", "No jugar con la cuota listada"),
        (r"\bRecheck only if the line improves or new information changes the edge\b", "Revisar solo si mejora la línea o nueva información cambia la ventaja"),
        (r"\bNo lineup/injury headline returned\b", "Sin titular de lesiones/alineación"),
        (r"\bNo SDIO event ID\b", "Sin ID de evento SDIO"),
        (r"\bAPI-FB: no fixture match\b", "API-FB: sin coincidencia de partido"),
        (r"\bAPI-FB lookup checked; no fixture match\b", "API-FB revisada; sin coincidencia de partido"),
        (r"\bWeather\b", "Clima"), (r"\bwind\b", "viento"), (r"\bLocation\b", "Ubicación"),
        (r"\bNews\b", "Noticias"), (r"\bsunny\b", "soleado"),
    )
    for old, new in replacements:
        text = re.sub(old, new, text, flags=re.I)
    return text


def _renderer_spanish_fallbacks() -> dict[str, str]:
    return {
        "Negative edge at current price.": "Ventaja negativa con la cuota actual.",
        "Do not play unless price improves.": "No jugar salvo que la cuota mejore.",
        "Recheck odds and key news.": "Revisar cuotas y noticias clave.",
        "Do not chain negative-EV picks.": "No encadenar señales con VE negativo.",
        "Avoid parlays unless edge turns positive.": "Evitar parlays salvo que la ventaja sea positiva.",
        "Recheck price before including.": "Revisar la cuota antes de incluir.",
        "Price check required before entry.": "Revisar cuota antes de entrar.",
        "Straight only: research": "Solo directa: investigación",
        "Do not combine without official verification": "No combinar sin verificación oficial",
        "Wait for better context or price": "Esperar mejor contexto o mejor cuota",
        "Risk status": "Estado de riesgo",
        "Recheck odds before entry.": "Revisar cuotas antes de entrar.",
        "Avoid if key news changes": "Evitar si cambian noticias clave",
        "Use only if the line remains playable and key news does not change.": "Usar solo si la línea sigue jugable y no cambian noticias clave.",
    }


def _install_renderer_es_fallbacks(module: Any) -> None:
    es = getattr(module, "ES", None)
    if isinstance(es, dict):
        es.update(_renderer_spanish_fallbacks())


def _alias_text(row: dict[str, Any], keys: tuple[str, ...], default: str) -> str:
    existing = "\n".join(str(row.get(key, "")) for key in keys if _useful(row.get(key)))
    return _spanish_text(existing) if existing else default


def _spanish_report_defaults(row: dict[str, Any]) -> None:
    if not _is_spanish(row):
        return
    pick = _get(row, "public_pick", "prediction", "pick", "selection", default="esta selección")
    if not any(_useful(row.get(k)) for k in ("why_bullets", "why_pick", "analysis_summary", "reason", "explanation")):
        row["why_bullets"] = "\n".join([
            f"El modelo proyecta {_fmt_pct(_get(row, 'learned_model_probability', 'model_probability_clean', 'model_probability', 'final_probability'))} de probabilidad para {pick}.",
            f"La probabilidad implícita del mercado es {_fmt_pct(_get(row, 'market_probability', 'market_implied_probability'))}.",
            f"Ventaja medida: {_fmt_pct(_get(row, 'model_market_edge', 'edge'), signed=True)}.",
            f"Valor esperado: {_fmt_ev(_get(row, 'expected_value_per_unit', 'profit_expected_value', 'expected_value', 'ev'))}.",
        ])
    for key, value in list(row.items()):
        if isinstance(value, str):
            row[key] = _spanish_text(value)
    risk_keys = ("why_lose", "risk_reason", "hidden_risk", "risk_notes")
    parlay_keys = ("chain_notes", "main_read", "add_on_legs", "parlay_notes")
    final_keys = ("final_explanation", "action_reason", "recommendation_reason", "decision_reasons")
    risk_text = _alias_text(row, risk_keys, "Ventaja negativa con la cuota actual.\nNo jugar salvo que la cuota mejore.\nRevisar cuotas y noticias clave.")
    parlay_text = _alias_text(row, parlay_keys, "No encadenar señales con VE negativo.\nEvitar parlays salvo que la ventaja sea positiva.\nRevisar la cuota antes de incluir.")
    final_text = _alias_text(row, final_keys, "No jugar con la cuota listada. Revisar si mejora la línea.")
    if "nueva información cambia" in final_text or len(final_text) > 72:
        final_text = "No jugar con la cuota listada. Revisar si mejora la línea."
    for key in risk_keys:
        row[key] = risk_text
    for key in parlay_keys:
        row[key] = parlay_text
    for key in final_keys:
        row[key] = final_text
    if not _useful(row.get("data_source")) and not _useful(row.get("odds_source")):
        row["data_source"] = "fila cargada/en caché"


def enrich_row_with_live_api_data(row_like: Any, *, report_run_id: str | None = None, last_api_refresh_time: str | None = None) -> dict[str, Any]:
    row = _row(row_like)
    if row.get("_live_api_enriched") == ENRICHMENT_VERSION and row.get("report_source") == "final_enriched_picks_df":
        if _is_spanish(row):
            _spanish_report_defaults(row)
        return row
    report_run_id = report_run_id or f"aba_mag_{int(time.time())}_{_hash_payload(row)}"
    last_api_refresh_time = last_api_refresh_time or datetime.now(timezone.utc).isoformat(timespec="seconds")
    before = set(k for k, v in row.items() if _useful(v))
    _enrich_sportsdataio(row)
    _enrich_weather(row)
    _enrich_api_football(row)
    _enrich_news(row)
    _enrich_perplexity(row)
    _apply_truth_fields(row, report_run_id, last_api_refresh_time)
    if _is_spanish(row):
        _spanish_report_defaults(row)
    after = set(k for k, v in row.items() if _useful(v))
    added = sorted(after - before)
    row["_live_api_enriched"] = ENRICHMENT_VERSION
    if added:
        row["api_enrichment_fields"] = " · ".join(added[:12])
    return row


def _report_page_event_key(row: Mapping[str, Any]) -> str:
    event = _get(row, "public_event", "event", "event_name", "matchup")
    if not event:
        return ""
    key = event.lower()
    key = re.sub(r"\s+(?:at|vs|v|@)\s+", " vs ", key)
    key = re.sub(r"[^a-z0-9áéíóúüñ]+", " ", key)
    return re.sub(r"\s+", " ", key).strip()


def _report_page_priority(row: Mapping[str, Any]) -> int:
    lane = _get(row, "report_lane", "report_lane_v2").lower()
    action = _get(row, "consumer_action", "recommended_action", "public_action").lower()
    publish_ready = _get(row, "official_publish_ready", "publish_ready").lower() in {"true", "1", "yes"}
    return 0 if publish_ready or "official" in action or "oficial" in action or lane in {"best_play", "best play"} else 1


def _dedupe_report_page_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not any(_get(row, "report_language", "language", "lang") for row in rows):
        return rows
    unique: list[dict[str, Any]] = []
    index_by_key: dict[str, int] = {}
    priority_by_key: dict[str, int] = {}
    for row in rows:
        key = _report_page_event_key(row)
        if not key:
            unique.append(row)
            continue
        priority = _report_page_priority(row)
        if key in index_by_key:
            if priority < priority_by_key[key]:
                unique[index_by_key[key]] = row
                priority_by_key[key] = priority
            continue
        index_by_key[key] = len(unique)
        priority_by_key[key] = priority
        unique.append(row)
    return unique


def enrich_rows_with_live_api_data(rows: list[Any] | tuple[Any, ...]) -> list[dict[str, Any]]:
    report_run_id, refresh_time = _new_run_meta(rows)
    enriched = _dedupe_report_page_rows([enrich_row_with_live_api_data(row, report_run_id=report_run_id, last_api_refresh_time=refresh_time) for row in rows])
    _ensure_renderer_patch()
    return enriched


def build_final_enriched_picks_df(raw_picks_df: Any, force_refresh: bool = False) -> Any:
    if force_refresh:
        _CACHE.clear()
    try:
        import pandas as pd  # type: ignore
        frame = raw_picks_df.copy() if hasattr(raw_picks_df, "copy") else pd.DataFrame(raw_picks_df)
        return pd.DataFrame(enrich_rows_with_live_api_data(frame.to_dict("records")))
    except Exception:
        return enrich_rows_with_live_api_data(list(raw_picks_df or []))


def _headline_context_lines(row: Any) -> list[str]:
    return [resolve_magazine_context(_row(row))[1]]


def _truth_pairs(row: Any, lang: str) -> list[tuple[str, str]]:
    data = _row(row)
    pairs = [
        ("REPORT SOURCE", _get(data, "report_source", default="final_enriched_picks_df")),
        ("ODDS ROW", _get(data, "odds_source", default="UPLOADED_ROW")),
        ("CONTEXT", _get(data, "context_source", default="EMPTY_WITH_REASON")),
        ("RUN", _get(data, "report_run_id", default="no_run_id")[:22]),
        ("REFRESH", _get(data, "last_api_refresh_time", default="no_refresh")[:22]),
    ]
    if str(lang).lower().startswith("es"):
        return [(_spanish_text(label), _spanish_text(value)) for label, value in pairs]
    return pairs


def install(module: Any) -> Any:
    _install_renderer_es_fallbacks(module)

    original_tr = getattr(module, "_tr", None)
    if callable(original_tr) and not getattr(original_tr, _SPANISH_TR_MARKER, False):
        def tr(value: Any, lang: str) -> str:
            translated = original_tr(value, lang)
            return _spanish_text(translated) if str(lang).lower().startswith("es") else translated
        setattr(tr, _SPANISH_TR_MARKER, True)
        module._tr = tr

    if getattr(module, "_LIVE_API_ENRICHMENT_PATCHED_VERSION", "") == ENRICHMENT_VERSION:
        return module

    original_render = module.render_full_pick_magazine_page
    original_png = module._png
    original_team_snapshot = getattr(module, "_team_snapshot", None)

    def render(row_like: Any, *args: Any, **kwargs: Any):
        return original_render(enrich_row_with_live_api_data(row_like), *args, **kwargs)

    def render_png(row_like: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
        return original_png(module.render_full_pick_magazine_page(enrich_row_with_live_api_data(row_like), background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))

    def team_snapshot(img: Any, draw: Any, x: int, y: int, width: int, team: str, color: Any, lang: str, row_arg: Any | None = None, side_arg: str = "", *extra: Any, **kwargs: Any) -> None:
        if callable(original_team_snapshot):
            try:
                original_team_snapshot(img, draw, x, y, width, team, color, lang, row_arg, side_arg, *extra, **kwargs)
                return
            except TypeError:
                original_team_snapshot(img, draw, x, y, width, team, color, lang)
                return
        if hasattr(module, "_badge") and hasattr(module, "_fit") and hasattr(module, "_bullets_auto"):
            label = module._team_label(team, lang)
            module._badge(img, draw, label, x, y, 50, 50, color)
            draw.text((x + 66, y + 9), label.upper(), font=module._fit(label.upper(), width - 70, 25, 7, True), fill=color)
            row = enrich_row_with_live_api_data(row_arg or {})
            try:
                items = module._team_items(row, side_arg)
            except Exception:
                items = ["Datos no disponibles para este evento" if lang == "es" else "Data not returned for this event"]
            module._bullets_auto(draw, x, y + 76, items, width - 10, 165, color, 18, 10, 4, lang)

    module.render_full_pick_magazine_page = render
    module.render_full_pick_magazine_page_png = render_png
    module._team_snapshot = team_snapshot
    module._headline_context_lines = _headline_context_lines
    module._pairs = _truth_pairs
    module.enrich_row_with_live_api_data = enrich_row_with_live_api_data
    module.enrich_rows_with_live_api_data = enrich_rows_with_live_api_data
    module.build_final_enriched_picks_df = build_final_enriched_picks_df
    module.check_api_health = check_api_health
    if ENRICHMENT_VERSION not in str(getattr(module, "MAGAZINE_STYLE_VERSION", "")):
        module.MAGAZINE_STYLE_VERSION = f"{module.MAGAZINE_STYLE_VERSION}_{ENRICHMENT_VERSION}"
    module._LIVE_API_ENRICHMENT_VERSION = ENRICHMENT_VERSION
    module._LIVE_API_ENRICHMENT_PATCHED_VERSION = ENRICHMENT_VERSION
    return module


def _ensure_renderer_patch() -> None:
    try:
        import autonomous_betting_agent.magazine_book_export as magazine_book_export
        install(magazine_book_export)
    except Exception:
        pass


def _patch_importlib_reload() -> None:
    if getattr(importlib.reload, _RELOAD_MARKER, False):
        return
    original_reload = getattr(importlib, "_aba_original_reload", importlib.reload)
    setattr(importlib, "_aba_original_reload", original_reload)

    def reload_with_magazine_patch(module: Any) -> Any:
        reloaded = original_reload(module)
        if getattr(reloaded, "__name__", "") == "autonomous_betting_agent.magazine_book_export":
            return install(reloaded)
        return reloaded

    setattr(reload_with_magazine_patch, _RELOAD_MARKER, True)
    importlib.reload = reload_with_magazine_patch


_patch_importlib_reload()
_ensure_renderer_patch()
