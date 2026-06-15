from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Callable, Mapping

from .api_clients import WeatherAPIClient, WeatherAPIConfig
from .environment_intelligence import score_environment
from .sportsdataio import SportsDataIOClient, SportsDataIOConfig


FIFA_VENUE_OVERRIDES: dict[str, dict[str, str]] = {
    "2026-06-15T16:00:00Z|cape verde|spain": {"sede_fifa": "Atlanta Stadium", "estadio_real": "Mercedes-Benz Stadium", "ciudad_area": "Atlanta, Georgia", "pais_sede": "USA"},
    "2026-06-15T19:00:00Z|belgium|egypt": {"sede_fifa": "Seattle Stadium", "estadio_real": "Lumen Field", "ciudad_area": "Seattle, Washington", "pais_sede": "USA"},
    "2026-06-15T22:00:00Z|saudi arabia|uruguay": {"sede_fifa": "Miami Stadium", "estadio_real": "Hard Rock Stadium", "ciudad_area": "Miami Gardens, Florida", "pais_sede": "USA"},
    "2026-06-16T19:00:00Z|france|senegal": {"sede_fifa": "New York New Jersey Stadium", "estadio_real": "MetLife Stadium", "ciudad_area": "East Rutherford, New Jersey", "pais_sede": "USA"},
    "2026-06-16T22:00:00Z|iraq|norway": {"sede_fifa": "Boston Stadium", "estadio_real": "Gillette Stadium", "ciudad_area": "Foxborough, Massachusetts", "pais_sede": "USA"},
    "2026-06-17T01:00:00Z|algeria|argentina": {"sede_fifa": "Kansas City Stadium", "estadio_real": "GEHA Field at Arrowhead Stadium", "ciudad_area": "Kansas City, Missouri", "pais_sede": "USA"},
    "2026-06-17T04:00:00Z|austria|jordan": {"sede_fifa": "San Francisco Bay Area Stadium", "estadio_real": "Levi's Stadium", "ciudad_area": "Santa Clara, California", "pais_sede": "USA"},
    "2026-06-17T17:00:00Z|dr congo|portugal": {"sede_fifa": "Houston Stadium", "estadio_real": "NRG Stadium", "ciudad_area": "Houston, Texas", "pais_sede": "USA"},
    "2026-06-17T20:00:00Z|croatia|england": {"sede_fifa": "Dallas Stadium", "estadio_real": "AT&T Stadium", "ciudad_area": "Arlington, Texas", "pais_sede": "USA"},
    "2026-06-18T02:00:00Z|colombia|uzbekistan": {"sede_fifa": "Mexico City Stadium", "estadio_real": "Estadio Azteca", "ciudad_area": "Mexico City", "pais_sede": "Mexico"},
    "2026-06-18T19:00:00Z|bosnia & herzegovina|switzerland": {"sede_fifa": "Los Angeles Stadium", "estadio_real": "SoFi Stadium", "ciudad_area": "Inglewood, California", "pais_sede": "USA"},
    "2026-06-18T22:00:00Z|canada|qatar": {"sede_fifa": "BC Place Vancouver", "estadio_real": "BC Place", "ciudad_area": "Vancouver, British Columbia", "pais_sede": "Canada"},
    "2026-06-19T19:00:00Z|australia|usa": {"sede_fifa": "Seattle Stadium", "estadio_real": "Lumen Field", "ciudad_area": "Seattle, Washington", "pais_sede": "USA"},
    "2026-06-20T01:00:00Z|brazil|haiti": {"sede_fifa": "Philadelphia Stadium", "estadio_real": "Lincoln Financial Field", "ciudad_area": "Philadelphia, Pennsylvania", "pais_sede": "USA"},
    "2026-06-20T17:00:00Z|netherlands|sweden": {"sede_fifa": "Houston Stadium", "estadio_real": "NRG Stadium", "ciudad_area": "Houston, Texas", "pais_sede": "USA"},
    "2026-06-20T20:00:00Z|germany|ivory coast": {"sede_fifa": "Toronto Stadium", "estadio_real": "BMO Field", "ciudad_area": "Toronto, Ontario", "pais_sede": "Canada"},
    "2026-06-21T00:00:00Z|curaçao|ecuador": {"sede_fifa": "Kansas City Stadium", "estadio_real": "GEHA Field at Arrowhead Stadium", "ciudad_area": "Kansas City, Missouri", "pais_sede": "USA"},
    "2026-06-21T04:00:00Z|japan|tunisia": {"sede_fifa": "Estadio Monterrey", "estadio_real": "Estadio BBVA", "ciudad_area": "Guadalupe / Monterrey, Nuevo Leon", "pais_sede": "Mexico"},
    "2026-06-21T16:00:00Z|saudi arabia|spain": {"sede_fifa": "Atlanta Stadium", "estadio_real": "Mercedes-Benz Stadium", "ciudad_area": "Atlanta, Georgia", "pais_sede": "USA"},
    "2026-06-21T19:00:00Z|belgium|iran": {"sede_fifa": "Los Angeles Stadium", "estadio_real": "SoFi Stadium", "ciudad_area": "Inglewood, California", "pais_sede": "USA"},
    "2026-06-21T22:00:00Z|cape verde|uruguay": {"sede_fifa": "Miami Stadium", "estadio_real": "Hard Rock Stadium", "ciudad_area": "Miami Gardens, Florida", "pais_sede": "USA"},
    "2026-06-22T17:00:00Z|argentina|austria": {"sede_fifa": "Dallas Stadium", "estadio_real": "AT&T Stadium", "ciudad_area": "Arlington, Texas", "pais_sede": "USA"},
    "2026-06-22T21:00:00Z|france|iraq": {"sede_fifa": "Philadelphia Stadium", "estadio_real": "Lincoln Financial Field", "ciudad_area": "Philadelphia, Pennsylvania", "pais_sede": "USA"},
    "2026-06-23T03:00:00Z|algeria|jordan": {"sede_fifa": "San Francisco Bay Area Stadium", "estadio_real": "Levi's Stadium", "ciudad_area": "Santa Clara, California", "pais_sede": "USA"},
    "2026-06-23T17:00:00Z|portugal|uzbekistan": {"sede_fifa": "Houston Stadium", "estadio_real": "NRG Stadium", "ciudad_area": "Houston, Texas", "pais_sede": "USA"},
    "2026-06-23T20:00:00Z|england|ghana": {"sede_fifa": "Boston Stadium", "estadio_real": "Gillette Stadium", "ciudad_area": "Foxborough, Massachusetts", "pais_sede": "USA"},
    "2026-06-23T23:00:00Z|croatia|panama": {"sede_fifa": "Toronto Stadium", "estadio_real": "BMO Field", "ciudad_area": "Toronto, Ontario", "pais_sede": "Canada"},
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").lower().replace("-", " ").replace("_", " ").split())


def _float(value: Any) -> float | None:
    text = str(value or "").strip().replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _first(row: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    lowered = {str(key).lower().replace(" ", "_").replace("-", "_"): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower().replace(" ", "_").replace("-", "_"))
        if value not in (None, ""):
            return value
    return ""


def _nested_first(row: Mapping[str, Any] | None, names: tuple[str, ...]) -> Any:
    if not row:
        return ""
    direct = _first(row, names)
    if direct not in (None, ""):
        return direct
    for name in names:
        parts = [part for part in name.replace("-", "_").split("_") if part]
        if len(parts) < 2:
            continue
        current: Any = row
        for part in parts:
            if not isinstance(current, Mapping):
                current = None
                break
            match = next((key for key in current.keys() if str(key).lower() == part.lower()), None)
            current = current.get(match) if match is not None else None
        if current not in (None, ""):
            return current
    return ""


def _similarity(left: Any, right: Any) -> float:
    left_clean, right_clean = _clean(left), _clean(right)
    if not left_clean or not right_clean:
        return 0.0
    if left_clean == right_clean:
        return 1.0
    if left_clean in right_clean or right_clean in left_clean:
        return 0.92
    return SequenceMatcher(None, left_clean, right_clean).ratio()


def _iso_start_key(start: datetime | None, raw: str = "") -> str:
    if start is not None:
        return start.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    text = str(raw or "").strip()
    return text[:-6] + "Z" if text.endswith("+00:00") else text


def _teams_key(start: datetime | None, raw_start: str, left: str, right: str) -> str:
    teams = sorted([_clean(left), _clean(right)])
    return f"{_iso_start_key(start, raw_start)}|{teams[0]}|{teams[1]}"


def _blank_venue() -> dict[str, Any]:
    return {
        "venue_name": "",
        "venue_name_fifa": "",
        "venue_city": "",
        "venue_state": "",
        "venue_country": "",
        "venue_source": "not_available_from_feed",
        "venue_note": "Venue was not provided by the available API sources.",
        "sede_fifa": "",
        "estadio_real": "",
        "ciudad_area": "",
        "pais_sede": "",
        "fuente_sede": "not_available_from_feed",
    }


def _fifa_venue_override(home_team: str, away_team: str, start: datetime | None, raw_start: str) -> dict[str, Any] | None:
    row = FIFA_VENUE_OVERRIDES.get(_teams_key(start, raw_start, home_team, away_team))
    if not row:
        return None
    city_area = row.get("ciudad_area", "")
    city_parts = [part.strip() for part in city_area.split(",")]
    city = city_parts[0] if city_parts else ""
    state = ", ".join(city_parts[1:]) if len(city_parts) > 1 else ""
    return {
        "venue_name": row.get("estadio_real", ""),
        "venue_name_fifa": row.get("sede_fifa", ""),
        "venue_city": city,
        "venue_state": state,
        "venue_country": row.get("pais_sede", ""),
        "venue_source": "fifa_venue_override",
        "venue_note": "Neutral-site FIFA venue override matched by event teams and start time.",
        "sede_fifa": row.get("sede_fifa", ""),
        "estadio_real": row.get("estadio_real", ""),
        "ciudad_area": row.get("ciudad_area", ""),
        "pais_sede": row.get("pais_sede", ""),
        "fuente_sede": "fifa_venue_override",
    }


def _venue_from_team(record: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not record:
        return None
    venue_name = _nested_first(record, ("StadiumDetails_Name", "Stadium_Name", "VenueName", "Venue", "Stadium"))
    city = _nested_first(record, ("StadiumDetails_City", "Stadium_City", "VenueCity", "City", "School"))
    state = _nested_first(record, ("StadiumDetails_State", "Stadium_State", "VenueState", "State", "Province"))
    country = _nested_first(record, ("StadiumDetails_Country", "Stadium_Country", "VenueCountry", "Country"))
    if not any((venue_name, city, state, country)):
        return None
    city_area = ", ".join(str(part) for part in (city, state) if part)
    return {
        "venue_name": str(venue_name or ""),
        "venue_name_fifa": "",
        "venue_city": str(city or ""),
        "venue_state": str(state or ""),
        "venue_country": str(country or ""),
        "venue_source": "sportsdataio_home_team_metadata",
        "venue_note": "Venue inferred from SportsDataIO home-team metadata; neutral-site events may differ.",
        "sede_fifa": "",
        "estadio_real": str(venue_name or ""),
        "ciudad_area": city_area,
        "pais_sede": str(country or ""),
        "fuente_sede": "sportsdataio_home_team_metadata",
    }


def _venue_weather_location(venue: Mapping[str, Any], fallback: str) -> str:
    city_area = str(venue.get("ciudad_area") or "").strip()
    country = str(venue.get("pais_sede") or "").strip()
    if city_area:
        return ", ".join(part for part in (city_area, country) if part)
    city = str(venue.get("venue_city") or "").strip()
    state = str(venue.get("venue_state") or "").strip()
    if city:
        return ", ".join(part for part in (city, state or country) if part)
    return fallback


def sportsdataio_sport_from_odds(sport_key: str, sport_title: str = "") -> str | None:
    text = _clean(f"{sport_key} {sport_title}")
    if "wnba" in text:
        return "wnba"
    if "nfl" in text or "americanfootball nfl" in text:
        return "nfl"
    if "nba" in text or "basketball nba" in text:
        return "nba"
    if "mlb" in text or "baseball mlb" in text:
        return "mlb"
    if "nhl" in text or "icehockey nhl" in text:
        return "nhl"
    if "ncaaf" in text or "college football" in text or "americanfootball_ncaaf" in text:
        return "cfb"
    if "ncaab" in text or "college basketball" in text or "basketball_ncaab" in text:
        return "cbb"
    if "soccer" in text:
        return "soccer"
    return None


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(item) for item in payload if isinstance(item, Mapping)]
    if isinstance(payload, Mapping):
        for value in payload.values():
            if isinstance(value, list):
                return [dict(item) for item in value if isinstance(item, Mapping)]
        return [dict(payload)]
    return []


def _team_aliases(record: Mapping[str, Any]) -> set[str]:
    aliases: set[str] = set()
    simple_names = (
        "Name",
        "FullName",
        "TeamName",
        "Team",
        "City",
        "Key",
        "TeamKey",
        "School",
        "ShortName",
    )
    for name in simple_names:
        value = _nested_first(record, (name,))
        if value:
            aliases.add(_clean(value))
    city = _nested_first(record, ("City", "School"))
    nickname = _nested_first(record, ("Name", "TeamName"))
    if city and nickname:
        aliases.add(_clean(f"{city} {nickname}"))
    return {alias for alias in aliases if alias}


def _match_team(team: str, teams: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not team or not teams:
        return None
    best_score = 0.0
    best_record: dict[str, Any] | None = None
    for record in teams:
        aliases = _team_aliases(record)
        score = max((_similarity(team, alias) for alias in aliases), default=0.0)
        if score > best_score:
            best_score = score
            best_record = record
    return best_record if best_score >= 0.72 else None


def _win_pct(record: Mapping[str, Any] | None) -> float | None:
    if not record:
        return None
    direct = _float(_nested_first(record, ("Percentage", "WinningPercentage", "WinPercentage", "Pct", "WinPct")))
    if direct is not None:
        if direct > 1.0:
            direct /= 100.0
        if 0.0 <= direct <= 1.0:
            return direct
    wins = _float(_nested_first(record, ("Wins", "Win", "GamesWon")))
    losses = _float(_nested_first(record, ("Losses", "Loss", "GamesLost")))
    ties = _float(_nested_first(record, ("Ties", "Tie"))) or 0.0
    if wins is None or losses is None:
        return None
    total = wins + losses + ties
    if total <= 0:
        return None
    return (wins + 0.5 * ties) / total


def _stats_probability_for_pick(home_record: Mapping[str, Any] | None, away_record: Mapping[str, Any] | None, home_team: str, away_team: str, pick_name: str) -> tuple[float | None, str]:
    home_pct = _win_pct(home_record)
    away_pct = _win_pct(away_record)
    if home_pct is None and away_pct is None:
        return None, "SportsDataIO team records did not include usable win/loss percentages"
    if home_pct is not None and away_pct is not None:
        edge = max(-0.35, min(0.35, home_pct - away_pct))
        home_probability = max(0.35, min(0.75, 0.50 + edge * 0.45))
    elif home_pct is not None:
        home_probability = max(0.38, min(0.72, 0.50 + (home_pct - 0.50) * 0.35))
    else:
        away_probability = max(0.38, min(0.72, 0.50 + ((away_pct or 0.50) - 0.50) * 0.35))
        home_probability = 1.0 - away_probability

    if _similarity(pick_name, home_team) >= _similarity(pick_name, away_team):
        return round(home_probability, 6), "SportsDataIO team record strength"
    return round(1.0 - home_probability, 6), "SportsDataIO team record strength"


def _team_keys(record: Mapping[str, Any] | None) -> set[str]:
    if not record:
        return set()
    names = ("Team", "TeamKey", "Key", "Name", "FullName", "City", "TeamID", "GlobalTeamID")
    return {_clean(_nested_first(record, (name,))) for name in names if _nested_first(record, (name,))}


def _injury_team_match(injury: Mapping[str, Any], team_record: Mapping[str, Any] | None) -> bool:
    keys = _team_keys(team_record)
    if not keys:
        return False
    injury_values = {
        _clean(_nested_first(injury, ("Team",))),
        _clean(_nested_first(injury, ("TeamKey",))),
        _clean(_nested_first(injury, ("TeamID",))),
        _clean(_nested_first(injury, ("GlobalTeamID",))),
    }
    return bool(keys & {value for value in injury_values if value})


def _injury_score(injuries: list[dict[str, Any]], picked_record: Mapping[str, Any] | None) -> tuple[float | None, str, int]:
    if picked_record is None:
        return None, "SportsDataIO injuries skipped because picked team was not matched", 0
    team_injuries = [injury for injury in injuries if _injury_team_match(injury, picked_record)]
    if not team_injuries:
        return 100.0, "SportsDataIO injuries: no listed injuries for picked team", 0
    severe = 0
    watch = 0
    for injury in team_injuries:
        text = _clean(" ".join(str(_nested_first(injury, (name,))) for name in ("Status", "InjuryStatus", "GameStatus", "Practice", "BodyPart")))
        if any(token in text for token in ("out", "injured reserve", "ir", "doubtful", "inactive")):
            severe += 1
        elif any(token in text for token in ("questionable", "probable", "limited")):
            watch += 1
    score = max(45.0, 100.0 - severe * 7.5 - watch * 2.5)
    reason = f"SportsDataIO injuries: {len(team_injuries)} listed, {severe} severe, {watch} watch"
    return round(score, 2), reason, len(team_injuries)


def _event_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _forecast_days_for(start: datetime | None) -> int:
    if start is None:
        return 1
    delta_days = (start.date() - datetime.now(timezone.utc).date()).days
    return max(1, min(10, delta_days + 1))


def _location_from_team(record: Mapping[str, Any] | None, fallback_team: str) -> str:
    if not record:
        return fallback_team
    stadium_city = _nested_first(record, ("StadiumDetails_City", "Stadium_City", "VenueCity"))
    stadium_state = _nested_first(record, ("StadiumDetails_State", "Stadium_State", "VenueState"))
    city = _nested_first(record, ("City", "School"))
    state = _nested_first(record, ("State", "Province"))
    country = _nested_first(record, ("Country",))
    if stadium_city:
        return ", ".join(str(part) for part in (stadium_city, stadium_state or country) if part)
    if city:
        return ", ".join(str(part) for part in (city, state or country) if part)
    return fallback_team


def _weather_row(payload: Mapping[str, Any], start: datetime | None) -> dict[str, Any]:
    selected: Mapping[str, Any] = {}
    forecast = payload.get("forecast") if isinstance(payload.get("forecast"), Mapping) else {}
    days = forecast.get("forecastday") if isinstance(forecast.get("forecastday"), list) else []
    target_date = start.date().isoformat() if start else ""
    for day in days:
        if not isinstance(day, Mapping):
            continue
        if target_date and str(day.get("date", "")) != target_date:
            continue
        hours = day.get("hour") if isinstance(day.get("hour"), list) else []
        if hours and start:
            target_hour = start.hour
            hourly = [item for item in hours if isinstance(item, Mapping)]
            selected = min(hourly, key=lambda item: abs(int(str(item.get("time", "00:00"))[-5:-3] or 0) - target_hour), default={})
        if not selected:
            selected = day.get("day") if isinstance(day.get("day"), Mapping) else {}
        break
    if not selected:
        selected = payload.get("current") if isinstance(payload.get("current"), Mapping) else {}
    return {
        "temp_c": selected.get("temp_c") or selected.get("avgtemp_c"),
        "temp_f": selected.get("temp_f") or selected.get("avgtemp_f"),
        "wind_kph": selected.get("wind_kph") or selected.get("maxwind_kph"),
        "wind_mph": selected.get("wind_mph") or selected.get("maxwind_mph"),
        "gust_mph": selected.get("gust_mph"),
        "precip_mm": selected.get("precip_mm") or selected.get("totalprecip_mm"),
        "humidity": selected.get("humidity") or selected.get("avghumidity"),
        "condition_text": (selected.get("condition") or {}).get("text", "") if isinstance(selected.get("condition"), Mapping) else "",
    }


@dataclass
class LiveAPIContextBuilder:
    sportsdataio_key: str = ""
    weatherapi_key: str = ""
    sportsdataio_client_factory: Callable[[str], SportsDataIOClient] | None = None
    weather_client: WeatherAPIClient | None = None
    sportsdataio_auth_mode: str = "header"
    _sports_clients: dict[str, SportsDataIOClient] = field(default_factory=dict)
    _teams_cache: dict[str, tuple[list[dict[str, Any]], str]] = field(default_factory=dict)
    _injury_cache: dict[str, tuple[list[dict[str, Any]], str]] = field(default_factory=dict)
    _weather_cache: dict[tuple[str, int], tuple[dict[str, Any], str]] = field(default_factory=dict)

    def _sports_client(self, sport: str) -> SportsDataIOClient | None:
        if not self.sportsdataio_key and self.sportsdataio_client_factory is None:
            return None
        if sport not in self._sports_clients:
            if self.sportsdataio_client_factory is not None:
                self._sports_clients[sport] = self.sportsdataio_client_factory(sport)
            else:
                self._sports_clients[sport] = SportsDataIOClient(
                    SportsDataIOConfig(api_key=self.sportsdataio_key, sport=sport, auth_mode=self.sportsdataio_auth_mode)
                )
        return self._sports_clients[sport]

    def _weather_client(self) -> WeatherAPIClient | None:
        if self.weather_client is not None:
            return self.weather_client
        if not self.weatherapi_key:
            return None
        self.weather_client = WeatherAPIClient(WeatherAPIConfig(api_key=self.weatherapi_key))
        return self.weather_client

    def _teams(self, sport: str) -> tuple[list[dict[str, Any]], str]:
        if sport in self._teams_cache:
            return self._teams_cache[sport]
        client = self._sports_client(sport)
        if client is None:
            result = ([], "not_configured")
        else:
            try:
                result = (_records(client.teams(sport=sport)), "used")
            except Exception as exc:  # pragma: no cover - external API safety
                result = ([], f"error: {exc}")
        self._teams_cache[sport] = result
        return result

    def _injuries(self, sport: str) -> tuple[list[dict[str, Any]], str]:
        if sport in self._injury_cache:
            return self._injury_cache[sport]
        client = self._sports_client(sport)
        if client is None:
            result = ([], "not_configured")
        else:
            try:
                result = (_records(client.raw_endpoint("Injuries", sport=sport, subfeed="scores")), "used")
            except Exception as exc:  # pragma: no cover - external API safety
                result = ([], f"error: {exc}")
        self._injury_cache[sport] = result
        return result

    def _weather(self, location: str, start: datetime | None) -> tuple[dict[str, Any], str]:
        client = self._weather_client()
        days = _forecast_days_for(start)
        key = (_clean(location), days)
        if key in self._weather_cache:
            return self._weather_cache[key]
        if client is None:
            result = ({}, "not_configured")
        elif not location.strip():
            result = ({}, "no_location")
        else:
            try:
                payload = client.forecast(location=location, days=days)
                result = (_weather_row(payload if isinstance(payload, Mapping) else {}, start), "used")
            except Exception as exc:  # pragma: no cover - external API safety
                result = ({}, f"error: {exc}")
        self._weather_cache[key] = result
        return result

    def context_for_event(self, event: Any, *, pick_name: str) -> dict[str, Any]:
        sport_key = str(getattr(event, "sport_key", ""))
        sport_title = str(getattr(event, "sport_title", ""))
        home_team = str(getattr(event, "home_team", ""))
        away_team = str(getattr(event, "away_team", ""))
        raw_start = str(getattr(event, "commence_time", ""))
        start = _event_datetime(raw_start)
        context: dict[str, Any] = {
            "odds_api_source_used": "yes",
            "sportsdataio_source_used": "no",
            "sportsdataio_status": "not_configured" if not self.sportsdataio_key and self.sportsdataio_client_factory is None else "not_supported_sport",
            "stats_source_used": "no",
            "injury_source_used": "no",
            "weather_source_used": "no",
            "weatherapi_status": "not_configured" if not self.weatherapi_key and self.weather_client is None else "no_location",
        }
        context.update(_blank_venue())

        sdio_sport = sportsdataio_sport_from_odds(sport_key, sport_title)
        home_record: dict[str, Any] | None = None
        away_record: dict[str, Any] | None = None
        picked_record: dict[str, Any] | None = None
        if sdio_sport:
            teams, teams_status = self._teams(sdio_sport)
            home_record = _match_team(home_team, teams)
            away_record = _match_team(away_team, teams)
            picked_record = home_record if _similarity(pick_name, home_team) >= _similarity(pick_name, away_team) else away_record
            context.update(
                {
                    "sportsdataio_sport": sdio_sport,
                    "sportsdataio_status": teams_status,
                    "sportsdataio_team_metadata_used": "yes" if teams_status == "used" and (home_record or away_record) else "no",
                    "sportsdataio_home_team_matched": "yes" if home_record else "no",
                    "sportsdataio_away_team_matched": "yes" if away_record else "no",
                    "sportsdataio_home_city": _nested_first(home_record or {}, ("City", "School", "StadiumDetails_City")),
                    "sportsdataio_away_city": _nested_first(away_record or {}, ("City", "School", "StadiumDetails_City")),
                }
            )
            stats_probability, stats_reason = _stats_probability_for_pick(home_record, away_record, home_team, away_team, pick_name)
            context["stats_source_reason"] = stats_reason
            if stats_probability is not None:
                context["stats_probability"] = stats_probability
                context["stats_source_used"] = "yes"
                context["sportsdataio_source_used"] = "yes"

            injuries, injuries_status = self._injuries(sdio_sport)
            context["sportsdataio_injuries_status"] = injuries_status
            if injuries_status == "used":
                injury_score, injury_reason, injury_count = _injury_score(injuries, picked_record)
                context["injury_source_reason"] = injury_reason
                context["sportsdataio_picked_team_injury_count"] = injury_count
                if injury_score is not None:
                    context["injury_risk_score"] = injury_score
                    context["injury_source_used"] = "yes"
                    context["sportsdataio_source_used"] = "yes"
            else:
                context["injury_source_reason"] = f"SportsDataIO injuries unavailable: {injuries_status}"
                context["sportsdataio_picked_team_injury_count"] = 0

        venue_context = _fifa_venue_override(home_team, away_team, start, raw_start) or _venue_from_team(home_record)
        if venue_context:
            context.update(venue_context)

        fallback_location = _location_from_team(home_record, home_team)
        location = _venue_weather_location(context, fallback_location)
        weather_row, weather_status = self._weather(location, start)
        context["weather_location"] = location
        context["weatherapi_status"] = weather_status
        if weather_row and weather_status == "used":
            risk = score_environment({**weather_row, "sport": sport_title or sport_key}, sport=sport_title or sport_key)
            context.update(weather_row)
            context.update(
                {
                    "weather_risk_score": risk.weather_risk_score,
                    "weather_flag": risk.weather_flag,
                    "weather_reason": risk.weather_reason,
                    "weather_bet_adjustment": risk.weather_bet_adjustment,
                    "weather_source_used": "yes",
                }
            )
        return context
