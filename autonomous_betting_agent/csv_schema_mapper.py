from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

import pandas as pd

SCHEMA_READY = "SCHEMA_READY"
SCHEMA_PARTIAL = "SCHEMA_PARTIAL"
SCHEMA_MISSING_REQUIRED_FIELDS = "SCHEMA_MISSING_REQUIRED_FIELDS"
SCHEMA_UNSUPPORTED_SHAPE = "SCHEMA_UNSUPPORTED_SHAPE"

CANONICAL_FIELDS = [
    "event",
    "prediction",
    "market_type",
    "bookmaker",
    "decimal_odds",
    "model_probability",
]

OPTIONAL_CANONICAL_FIELDS = [
    "sportsbook",
    "event_start_utc",
    "odds_timestamp",
    "result",
    "stake_units",
    "league",
    "sport",
]

SCHEMA_MAPPER_COLUMNS = [
    "schema_mapper_status",
    "schema_mapper_missing_required_fields",
    "schema_mapper_detected_aliases",
    "schema_mapper_applied_mappings",
    "schema_mapper_unmapped_columns",
    "schema_mapper_repair_notes",
    "schema_mapper_duplicate_count",
    "schema_mapper_ready_for_advisory_pipeline",
]

ALIASES: dict[str, tuple[str, ...]] = {
    "event": (
        "event",
        "event_name",
        "game",
        "game_name",
        "match",
        "matchup",
        "fixture",
        "teams",
        "evento",
        "partido",
    ),
    "prediction": (
        "prediction",
        "pick",
        "selection",
        "team_pick",
        "bet_selection",
        "prediccion",
        "seleccion",
        "selección",
    ),
    "market_type": (
        "market_type",
        "market",
        "bet_type",
        "wager_type",
        "tipo_mercado",
        "mercado",
        "tipo_apuesta",
    ),
    "bookmaker": (
        "bookmaker",
        "sportsbook",
        "book",
        "book_name",
        "casino",
        "casa",
        "casa_apuestas",
    ),
    "sportsbook": (
        "sportsbook",
        "bookmaker",
        "book",
        "book_name",
        "casino",
        "casa",
        "casa_apuestas",
    ),
    "decimal_odds": (
        "decimal_odds",
        "odds_decimal",
        "odds",
        "price",
        "current_odds",
        "best_odds",
        "cuota",
        "momio_decimal",
        "momio",
    ),
    "model_probability": (
        "model_probability",
        "probability",
        "model_prob",
        "win_probability",
        "confidence",
        "prob",
        "probabilidad",
        "confianza",
    ),
    "event_start_utc": (
        "event_start_utc",
        "commence_time",
        "start_time",
        "game_time",
        "event_time",
        "fecha",
        "hora_inicio",
    ),
    "odds_timestamp": (
        "odds_timestamp",
        "last_update",
        "price_time",
        "updated_at",
        "timestamp",
    ),
    "result": (
        "result",
        "grade",
        "outcome",
        "pick_result",
        "result_status",
        "resultado",
        "estado_resultado",
    ),
    "stake_units": (
        "stake_units",
        "units",
        "stake",
        "risk_units",
        "unidades",
    ),
    "league": ("league", "competition", "liga", "competicion", "competición"),
    "sport": ("sport", "deporte"),
}

RESULT_ALIASES = {
    "w": "win",
    "won": "win",
    "win": "win",
    "ganada": "win",
    "ganó": "win",
    "gano": "win",
    "l": "loss",
    "lost": "loss",
    "loss": "loss",
    "perdida": "loss",
    "perdió": "loss",
    "perdio": "loss",
    "push": "push",
    "tie": "push",
    "draw": "push",
    "void": "cancel",
    "cancel": "cancel",
    "cancelled": "cancel",
    "canceled": "cancel",
    "pending": "pending",
    "open": "pending",
}

MARKET_ALIASES = {
    "moneyline": "h2h",
    "ml": "h2h",
    "winner": "h2h",
    "ganador": "h2h",
    "spread": "spreads",
    "handicap": "spreads",
    "total": "totals",
    "over_under": "totals",
    "over/under": "totals",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"none", "nan", "null", "nat", ""} else text


def _column_key(column: Any) -> str:
    return _text(column).lower().strip().replace(" ", "_").replace("-", "_")


def _to_float_text(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    return text.replace("%", "").replace(" ", "").replace(",", "")


def normalize_decimal_odds(value: Any) -> float | None:
    text = _to_float_text(value)
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if number <= 0:
        return None
    if number >= 100:
        return round(number / 100 + 1, 6)
    if number <= -100:
        return round(100 / abs(number) + 1, 6)
    if number > 1:
        return round(number, 6)
    return None


def normalize_probability(value: Any) -> float | None:
    text = _text(value)
    if not text:
        return None
    is_percent = "%" in text
    try:
        number = float(text.replace("%", "").replace(" ", "").replace(",", ""))
    except ValueError:
        return None
    if is_percent or number > 1:
        number = number / 100
    if 0 <= number <= 1:
        return round(number, 6)
    return None


def normalize_result(value: Any) -> str:
    key = _text(value).lower().strip().replace(" ", "_").replace("-", "_")
    return RESULT_ALIASES.get(key, _text(value))


def normalize_market(value: Any) -> str:
    key = _text(value).lower().strip().replace(" ", "_").replace("-", "_")
    return MARKET_ALIASES.get(key, _text(value))


def detect_column_mappings(columns: Sequence[Any]) -> dict[str, str]:
    keyed = {_column_key(column): str(column) for column in columns}
    mappings: dict[str, str] = {}
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            key = _column_key(alias)
            if key in keyed:
                mappings[canonical] = keyed[key]
                break
    return mappings


def _mapping_notes(mappings: Mapping[str, str]) -> tuple[str, str]:
    detected = []
    applied = []
    for canonical, source in mappings.items():
        if canonical != source:
            detected.append(f"{source}->{canonical}")
        applied.append(f"{source}->{canonical}")
    return ",".join(detected), ",".join(applied)


def _duplicate_count(frame: pd.DataFrame) -> int:
    keys = [field for field in ["event", "prediction", "market_type", "bookmaker", "event_start_utc"] if field in frame.columns]
    if not keys or frame.empty:
        return 0
    return int(frame.duplicated(subset=keys, keep=False).sum())


def _repair_status(missing: Sequence[str], duplicate_count: int) -> tuple[str, bool]:
    if len(missing) == len(CANONICAL_FIELDS):
        return SCHEMA_UNSUPPORTED_SHAPE, False
    if missing:
        return SCHEMA_MISSING_REQUIRED_FIELDS, False
    if duplicate_count:
        return SCHEMA_PARTIAL, True
    return SCHEMA_READY, True


def map_and_repair_frame(frame: pd.DataFrame | None) -> pd.DataFrame:
    if frame is None or frame.empty:
        out = pd.DataFrame(columns=CANONICAL_FIELDS + SCHEMA_MAPPER_COLUMNS)
        out["schema_mapper_status"] = SCHEMA_UNSUPPORTED_SHAPE
        out["schema_mapper_ready_for_advisory_pipeline"] = False
        return out

    original = frame.copy(deep=True)
    mappings = detect_column_mappings(list(original.columns))
    repaired = pd.DataFrame(index=original.index)

    for canonical in CANONICAL_FIELDS + OPTIONAL_CANONICAL_FIELDS:
        source = mappings.get(canonical)
        if source and source in original.columns:
            repaired[canonical] = original[source]

    if "sportsbook" not in repaired.columns and "bookmaker" in repaired.columns:
        repaired["sportsbook"] = repaired["bookmaker"]
    if "bookmaker" not in repaired.columns and "sportsbook" in repaired.columns:
        repaired["bookmaker"] = repaired["sportsbook"]

    if "decimal_odds" in repaired.columns:
        repaired["decimal_odds"] = repaired["decimal_odds"].map(normalize_decimal_odds)
    if "model_probability" in repaired.columns:
        repaired["model_probability"] = repaired["model_probability"].map(normalize_probability)
    if "result" in repaired.columns:
        repaired["result"] = repaired["result"].map(normalize_result)
    if "market_type" in repaired.columns:
        repaired["market_type"] = repaired["market_type"].map(normalize_market)
        repaired["market"] = repaired["market_type"]

    for column in original.columns:
        if column not in repaired.columns and column not in mappings.values():
            repaired[column] = original[column]

    missing = [field for field in CANONICAL_FIELDS if field not in repaired.columns or repaired[field].isna().all() or repaired[field].map(_text).eq("").all()]
    duplicate_count = _duplicate_count(repaired)
    status, ready = _repair_status(missing, duplicate_count)
    detected, applied = _mapping_notes(mappings)
    unmapped = [str(column) for column in original.columns if str(column) not in mappings.values() and str(column) not in repaired.columns]
    notes = [
        "Local/session-only CSV schema mapping. Original upload is not modified in place.",
        "Decimal odds, probabilities, result labels, market aliases, and duplicate rows/events are normalized or diagnosed when possible.",
        "No server, database, proof mutation, result grading mutation, official lock change, stake change, bankroll action, or live betting action is performed.",
    ]
    repaired["schema_mapper_status"] = status
    repaired["schema_mapper_missing_required_fields"] = ",".join(missing)
    repaired["schema_mapper_detected_aliases"] = detected
    repaired["schema_mapper_applied_mappings"] = applied
    repaired["schema_mapper_unmapped_columns"] = ",".join(unmapped)
    repaired["schema_mapper_repair_notes"] = " ".join(notes)
    repaired["schema_mapper_duplicate_count"] = duplicate_count
    repaired["schema_mapper_ready_for_advisory_pipeline"] = bool(ready)
    return repaired.reset_index(drop=True)


def schema_mapper_summary(frame: pd.DataFrame | None) -> pd.DataFrame:
    repaired = map_and_repair_frame(frame)
    if repaired.empty:
        return pd.DataFrame(columns=["schema_mapper_status", "row_count", "ready_rows", "duplicate_rows", "missing_required_fields"])
    ready = repaired.get("schema_mapper_ready_for_advisory_pipeline", pd.Series(dtype=bool)).fillna(False).astype(bool)
    return pd.DataFrame([{
        "schema_mapper_status": str(repaired.get("schema_mapper_status", pd.Series([SCHEMA_UNSUPPORTED_SHAPE])).iloc[0]),
        "row_count": int(len(repaired)),
        "ready_rows": int(ready.sum()),
        "duplicate_rows": int(repaired.get("schema_mapper_duplicate_count", pd.Series([0])).iloc[0] or 0),
        "missing_required_fields": str(repaired.get("schema_mapper_missing_required_fields", pd.Series([""])).iloc[0] or ""),
    }])


def schema_mapper_report_section(frame: pd.DataFrame | None) -> str:
    repaired = map_and_repair_frame(frame)
    summary = schema_mapper_summary(frame).iloc[0].to_dict()
    return "\n".join([
        "CSV Schema Mapper + Upload Assistant",
        "- Local/session-only mapping and export. Original upload is not modified in place.",
        f"- Status: {summary.get('schema_mapper_status')}; rows: {summary.get('row_count')}; ready rows: {summary.get('ready_rows')}.",
        f"- Duplicate rows/events detected: {summary.get('duplicate_rows')}.",
        f"- Missing required fields: {summary.get('missing_required_fields') or 'none'}.",
        "- Safety: no server, no database, no proof mutation, no grading mutation, no official lock change, no stake/bankroll action, no live betting.",
    ])
