from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import pandas as pd

RESULT_ALIASES = {
    "w": "win",
    "won": "win",
    "win": "win",
    "winner": "win",
    "ganada": "win",
    "ganado": "win",
    "l": "loss",
    "lost": "loss",
    "loss": "loss",
    "loser": "loss",
    "perdida": "loss",
    "perdido": "loss",
    "push": "push",
    "tie": "push",
    "draw": "push",
    "void": "cancel",
    "cancel": "cancel",
    "cancelled": "cancel",
    "canceled": "cancel",
    "pending": "pending",
    "open": "pending",
    "": "pending",
}

PLAYABLE_STATUS = "playable"
WATCHLIST_STATUS = "watchlist"
AVOID_STATUS = "avoid"
PREDICTION_ONLY_STATUS = "prediction_only"

POSITIVE_MARKERS = ("playable", "official +ev", "official ev", "publish ready", "client ready", "green")
WATCHLIST_MARKERS = ("watchlist", "price watch", "watch", "monitor")
PREDICTION_ONLY_MARKERS = ("prediction only", "prediction-only", "research", "learning", "analysis only", "informational")
BLOCKED_MARKERS = ("blocked", "avoid", "no play", "not playable", "removed", "unsafe", "missing", "red flag")
TRUE_VALUES = {"1", "true", "yes", "y", "ready", "published", "pass", "passed", "complete", "completed"}


@dataclass(frozen=True)
class RowProfitability:
    status: str
    result: str
    event_key: str
    decimal_odds: float | None
    model_probability: float | None
    market_probability: float | None
    edge: float | None
    no_vig_edge: float | None
    expected_value: float | None
    clv: float | None
    stake_units: float
    profit_units: float
    settled_stake_units: float
    odds_verified: bool
    blocker: str


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"none", "nan", "null", "nat"} else text


def _lower(value: Any) -> str:
    return _safe_text(value).lower()


def _truthy(value: Any) -> bool:
    return _lower(value) in TRUE_VALUES


def _float(value: Any) -> float | None:
    text = _safe_text(value)
    if not text:
        return None
    text = text.replace("%", "").replace(",", "").strip()
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    try:
        if pd.isna(parsed):
            return None
    except TypeError:
        return None
    return parsed


def _first(row: Mapping[str, Any], names: Sequence[str]) -> Any:
    for name in names:
        if name in row:
            value = row.get(name)
            if _safe_text(value):
                return value
    return None


def _first_float(row: Mapping[str, Any], names: Sequence[str]) -> float | None:
    for name in names:
        value = _float(row.get(name))
        if value is not None:
            return value
    return None


def _as_frame(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None) -> pd.DataFrame:
    if rows is None:
        return pd.DataFrame()
    if isinstance(rows, pd.DataFrame):
        return rows.copy(deep=True)
    return pd.DataFrame(list(rows))


def probability(value: Any) -> float | None:
    parsed = _float(value)
    if parsed is None:
        return None
    if parsed > 1:
        parsed = parsed / 100
    return parsed if 0 <= parsed <= 1 else None


def decimal_odds(value: Any) -> float | None:
    parsed = _float(value)
    if parsed is None:
        return None
    if parsed >= 100:
        return round(parsed / 100 + 1, 6)
    if parsed <= -100:
        return round(100 / abs(parsed) + 1, 6)
    return parsed if parsed > 1 else None


def implied_probability_from_odds(odds: float | None) -> float | None:
    if odds is None or odds <= 1:
        return None
    return 1 / odds


def normalize_result(value: Any) -> str:
    key = _lower(value).replace(" ", "_").replace("-", "_")
    return RESULT_ALIASES.get(key, key or "pending")


def event_key(row: Mapping[str, Any]) -> str:
    for name in ("proof_id", "event_id", "event", "public_event", "event_name", "matchup", "game", "fixture"):
        value = _safe_text(row.get(name))
        if value:
            return value
    return ""


def pick_key(row: Mapping[str, Any]) -> str:
    return "|".join(
        _safe_text(_first(row, names))
        for names in (
            ("event", "public_event", "event_name", "matchup", "game", "fixture"),
            ("prediction", "public_pick", "pick", "selection"),
            ("market_type", "market", "market_name"),
            ("bookmaker", "sportsbook", "book"),
        )
    )


def _combined_status_text(row: Mapping[str, Any]) -> str:
    fields = (
        "advisory_status",
        "official_status_label",
        "official_publish_status",
        "publish_status",
        "report_lane",
        "report_lane_v2",
        "recommended_action",
        "consumer_action",
        "learning_status",
        "data_issue_reason",
        "blocked_reason",
        "blocker",
        "blockers",
        "market_blocker",
    )
    return " | ".join(_safe_text(row.get(field)) for field in fields if _safe_text(row.get(field))).lower()


def blocker_reason(row: Mapping[str, Any]) -> str:
    for name in ("data_issue_reason", "blocked_reason", "blocker", "blockers", "market_blocker", "schema_mapper_missing_required_fields"):
        value = _safe_text(row.get(name))
        if value:
            return value
    status_text = _combined_status_text(row)
    return "blocked marker" if any(marker in status_text for marker in BLOCKED_MARKERS) else ""
