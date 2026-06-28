from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

import pandas as pd

REAL_SPORTSBOOK = "REAL_SPORTSBOOK"
CONSENSUS_ONLY = "CONSENSUS_ONLY"
UNKNOWN_SOURCE = "UNKNOWN_SOURCE"

LINE_SHOPPING_AVAILABLE = "LINE_SHOPPING_AVAILABLE"
LINE_SHOPPING_UNAVAILABLE_CONSENSUS_ONLY = "LINE_SHOPPING_UNAVAILABLE_CONSENSUS_ONLY"
LINE_SHOPPING_UNAVAILABLE_ONE_BOOK = "LINE_SHOPPING_UNAVAILABLE_ONE_BOOK"
LINE_SHOPPING_UNAVAILABLE_UNKNOWN_SOURCE = "LINE_SHOPPING_UNAVAILABLE_UNKNOWN_SOURCE"
LINE_SHOPPING_UNAVAILABLE_MISSING_PRICE = "LINE_SHOPPING_UNAVAILABLE_MISSING_PRICE"

SPORTSBOOK_FIELDS = [
    "bookmaker",
    "sportsbook",
    "book",
    "book_name",
    "odds_source",
    "provider",
    "source",
    "sportsbook_name",
    "casino",
    "bookie",
]
DECIMAL_ODDS_FIELDS = ["decimal_price", "decimal_odds", "price_decimal", "odds_decimal", "odds", "price", "advisory_current_decimal_odds"]
EVENT_FIELDS = ["event_id", "game_id", "matchup", "event", "event_name", "game"]
MARKET_FIELDS = ["market_type", "market", "bet_type"]
SELECTION_FIELDS = ["selection", "prediction", "pick", "public_pick", "outcome", "name", "team"]
LINE_FIELDS = ["line", "point", "points", "spread", "handicap", "total", "total_points"]

CONSENSUS_CANONICAL = {
    "consensus",
    "consensus_average",
    "average",
    "market_average",
    "aggregated",
    "aggregate",
    "median",
    "market_consensus",
    "consensus_price",
}
UNKNOWN_CANONICAL = {"", "unknown", "none", "nan", "null", "n/a", "na"}
KNOWN_SPORTSBOOK_PREFIXES = {
    "caliente": "caliente",
    "playdoit": "playdoit",
    "codere": "codere",
    "bet365": "bet365",
    "betcris": "betcris",
    "novibet": "novibet",
    "strendus": "strendus",
    "winpot": "winpot",
    "rushbet": "rushbet",
    "betway": "betway",
}
NICE_DISPLAY = {
    "caliente": "Caliente",
    "bet365": "Bet365",
    "betcris": "Betcris",
    "novibet": "Novibet",
    "strendus": "Strendus",
    "winpot": "Winpot",
    "rushbet": "Rushbet",
    "betway": "Betway",
}

SOURCE_FIELD_NAMES = [
    "advisory_original_sportsbook_label",
    "advisory_normalized_sportsbook",
    "advisory_sportsbook_source_type",
    "advisory_is_real_sportsbook",
    "advisory_is_consensus_source",
    "advisory_line_shopping_source_status",
    "advisory_line_shopping_source_reason",
]


def _records(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame | None) -> list[dict[str, Any]]:
    if rows_or_frame is None:
        return []
    if isinstance(rows_or_frame, pd.DataFrame):
        return rows_or_frame.to_dict("records")
    return [deepcopy(dict(row)) for row in rows_or_frame if isinstance(row, Mapping)]


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("-", "_").replace(" ", "_").replace("/", "_")
    while "__" in text:
        text = text.replace("__", "_")
    return text.strip("_")


def _display_label(value: Any, canonical: str) -> str:
    text = str(value or "").strip()
    if text:
        if canonical in NICE_DISPLAY and text.lower() == canonical:
            return NICE_DISPLAY[canonical]
        return text
    return ""


def _first_text(row: Mapping[str, Any], fields: Sequence[str]) -> str:
    for field in fields:
        if field not in row:
            continue
        value = row.get(field)
        text = str(value or "").strip()
        if text and _norm(text) not in UNKNOWN_CANONICAL:
            return text
    return ""


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    if _norm(text) in UNKNOWN_CANONICAL:
        return None
    try:
        parsed = float(text)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 1.0 else None


def _decimal_odds(row: Mapping[str, Any]) -> float | None:
    for field in DECIMAL_ODDS_FIELDS:
        value = _to_float(row.get(field))
        if value is not None:
            return value
    return None


def _identity(row: Mapping[str, Any], fields: Sequence[str], default: str) -> str:
    text = _first_text(row, fields)
    return _norm(text) or default


def _selection_group_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        _identity(row, EVENT_FIELDS, "unknown_event"),
        _identity(row, MARKET_FIELDS, "unknown_market"),
        _identity(row, SELECTION_FIELDS, "unknown_selection"),
        _identity(row, LINE_FIELDS, ""),
    )


def normalize_sportsbook_source(value: Any) -> dict[str, Any]:
    original = "" if value is None else str(value).strip()
    normalized = _norm(original)
    if normalized in UNKNOWN_CANONICAL:
        source_type = UNKNOWN_SOURCE
        canonical = "unknown"
    elif normalized in CONSENSUS_CANONICAL:
        source_type = CONSENSUS_ONLY
        canonical = normalized
    else:
        canonical = normalized
        for prefix, mapped in KNOWN_SPORTSBOOK_PREFIXES.items():
            if normalized == prefix or normalized.startswith(f"{prefix}_"):
                canonical = mapped
                break
        source_type = REAL_SPORTSBOOK
    return {
        "original_label": _display_label(original, canonical),
        "normalized_sportsbook": canonical,
        "source_type": source_type,
        "is_real_sportsbook": source_type == REAL_SPORTSBOOK,
        "is_consensus_source": source_type == CONSENSUS_ONLY,
    }


def detect_sportsbook_source(row: Mapping[str, Any]) -> dict[str, Any]:
    label = _first_text(row, SPORTSBOOK_FIELDS)
    return normalize_sportsbook_source(label)


def _base_status(row: Mapping[str, Any]) -> tuple[str, str]:
    price = _decimal_odds(row)
    source_type = str(row.get("advisory_sportsbook_source_type") or UNKNOWN_SOURCE)
    if price is None:
        return LINE_SHOPPING_UNAVAILABLE_MISSING_PRICE, "missing_price"
    if source_type == UNKNOWN_SOURCE:
        return LINE_SHOPPING_UNAVAILABLE_UNKNOWN_SOURCE, "source_is_unknown_or_missing"
    if source_type == CONSENSUS_ONLY:
        return LINE_SHOPPING_UNAVAILABLE_CONSENSUS_ONLY, "line_shopping_unavailable_consensus_only"
    return LINE_SHOPPING_UNAVAILABLE_ONE_BOOK, "only_one_real_sportsbook_detected"


def add_sportsbook_source_fields(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame | None) -> list[dict[str, Any]]:
    rows = _records(rows_or_frame)
    if not rows:
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        item = deepcopy(row)
        source = detect_sportsbook_source(item)
        item.update({
            "advisory_original_sportsbook_label": source["original_label"],
            "advisory_normalized_sportsbook": source["normalized_sportsbook"],
            "advisory_sportsbook_source_type": source["source_type"],
            "advisory_is_real_sportsbook": bool(source["is_real_sportsbook"]),
            "advisory_is_consensus_source": bool(source["is_consensus_source"]),
        })
        status, reason = _base_status(item)
        item["advisory_line_shopping_source_status"] = status
        item["advisory_line_shopping_source_reason"] = reason
        out.append(item)

    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for item in out:
        groups.setdefault(_selection_group_key(item), []).append(item)

    for group in groups.values():
        real_books = {str(row.get("advisory_normalized_sportsbook")) for row in group if row.get("advisory_is_real_sportsbook") and _decimal_odds(row) is not None}
        real_with_price = [row for row in group if row.get("advisory_is_real_sportsbook") and _decimal_odds(row) is not None]
        best_real = None
        if real_with_price:
            best_real = max(real_with_price, key=lambda row: (_decimal_odds(row) or 0.0, str(row.get("advisory_original_sportsbook_label") or "")))
        if len(real_books) >= 2:
            for row in group:
                if row.get("advisory_is_real_sportsbook") and _decimal_odds(row) is not None:
                    row["advisory_line_shopping_source_status"] = LINE_SHOPPING_AVAILABLE
                    row["advisory_line_shopping_source_reason"] = "two_or_more_real_sportsbooks_available"
        if best_real is not None:
            best_odds = _decimal_odds(best_real)
            best_book = str(best_real.get("advisory_original_sportsbook_label") or best_real.get("advisory_normalized_sportsbook") or "")
            for row in group:
                if best_odds is not None:
                    row["advisory_best_available_decimal_odds"] = round(float(best_odds), 6)
                    row["advisory_best_available_sportsbook"] = best_book
                    current = _decimal_odds(row)
                    probability = _to_float(row.get("model_probability") or row.get("model_probability_clean") or row.get("final_probability") or row.get("probability") or row.get("confidence_probability"))
                    if current is not None:
                        gain = float(best_odds) - float(current)
                        row["advisory_line_shopping_gain"] = round(gain, 6)
                        row["advisory_line_shopping_gain_pct"] = round(gain / float(current), 6) if current > 0 else None
                    if probability is not None:
                        if probability > 1.0 and probability <= 100.0:
                            probability = probability / 100.0
                        row["advisory_best_price_EV"] = round(float(probability) * float(best_odds) - 1.0, 6)
        else:
            for row in group:
                if row.get("advisory_is_consensus_source") or row.get("advisory_sportsbook_source_type") == UNKNOWN_SOURCE:
                    row["advisory_best_available_sportsbook"] = ""
                    row["advisory_best_available_decimal_odds"] = None
                    row["advisory_best_price_EV"] = None
                    row["advisory_line_shopping_gain"] = None
                    row["advisory_line_shopping_gain_pct"] = None

    for row in out:
        status = str(row.get("advisory_playable_status") or "")
        source_type = str(row.get("advisory_sportsbook_source_type") or UNKNOWN_SOURCE)
        if status == "PLAYABLE_PLUS_EV" and source_type == CONSENSUS_ONLY:
            row["advisory_playable_status"] = "WATCHLIST_VALUE"
            row["advisory_playable_reason"] = "source_is_consensus_not_real_sportsbook"
            row["advisory_prediction_only_reason"] = row.get("advisory_prediction_only_reason") or "Consensus/average price is not a real sportsbook price."
            row["advisory_odds_value_tier"] = "WATCHLIST"
        elif status == "PLAYABLE_PLUS_EV" and source_type == UNKNOWN_SOURCE:
            row["advisory_playable_status"] = "WATCHLIST_VALUE"
            row["advisory_playable_reason"] = "source_is_unknown_or_missing"
            row["advisory_prediction_only_reason"] = row.get("advisory_prediction_only_reason") or "Sportsbook source is missing or unknown."
            row["advisory_odds_value_tier"] = "WATCHLIST"
    return out


def sportsbook_source_summary(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame | None) -> pd.DataFrame:
    rows = add_sportsbook_source_fields(rows_or_frame)
    if not rows:
        return pd.DataFrame(columns=[
            "advisory_sportsbook_source_type",
            "advisory_normalized_sportsbook",
            "original_display_labels",
            "row_count",
            "counted_for_line_shopping",
            "reason",
        ])
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row.get("advisory_sportsbook_source_type") or UNKNOWN_SOURCE), str(row.get("advisory_normalized_sportsbook") or "unknown"))
        bucket = buckets.setdefault(key, {
            "advisory_sportsbook_source_type": key[0],
            "advisory_normalized_sportsbook": key[1],
            "labels": set(),
            "row_count": 0,
            "counted_for_line_shopping": key[0] == REAL_SPORTSBOOK,
            "reason": "real_sportsbook_price" if key[0] == REAL_SPORTSBOOK else "consensus_is_context_only_not_real_sportsbook" if key[0] == CONSENSUS_ONLY else "source_is_unknown_or_missing",
        })
        label = str(row.get("advisory_original_sportsbook_label") or "")
        if label:
            bucket["labels"].add(label)
        bucket["row_count"] += 1
    records = []
    for bucket in buckets.values():
        records.append({
            "advisory_sportsbook_source_type": bucket["advisory_sportsbook_source_type"],
            "advisory_normalized_sportsbook": bucket["advisory_normalized_sportsbook"],
            "original_display_labels": ", ".join(sorted(bucket["labels"])) or "",
            "row_count": int(bucket["row_count"]),
            "counted_for_line_shopping": bool(bucket["counted_for_line_shopping"]),
            "reason": bucket["reason"],
        })
    return pd.DataFrame(records).sort_values(["advisory_sportsbook_source_type", "advisory_normalized_sportsbook"], ignore_index=True)


def sportsbook_source_counts(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame | None) -> dict[str, int]:
    rows = add_sportsbook_source_fields(rows_or_frame)
    return {
        "real_sportsbook_count": sum(1 for row in rows if row.get("advisory_sportsbook_source_type") == REAL_SPORTSBOOK),
        "consensus_only_count": sum(1 for row in rows if row.get("advisory_sportsbook_source_type") == CONSENSUS_ONLY),
        "unknown_source_count": sum(1 for row in rows if row.get("advisory_sportsbook_source_type") == UNKNOWN_SOURCE),
    }
