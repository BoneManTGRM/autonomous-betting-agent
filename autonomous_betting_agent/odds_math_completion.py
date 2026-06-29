from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.value_math import assess_value_pick, normalize_probability, safe_float

SCHEMA_VERSION = "odds_math_completion_v1"
GREEN = "GREEN"
YELLOW = "YELLOW"
RED = "RED"
DATA_WARNING = "DATA WARNING"
NO_BET = "NO BET"
WAIT = "WAIT FOR BETTER ODDS"
WATCH = "WATCH ONLY"
PLAY = "PLAYABLE VALUE"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash(prefix: str, value: Any, length: int = 24) -> str:
    return f"{prefix}_{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()[:length]}"


def parse_csv_text(csv_text: str | None) -> list[dict[str, str]]:
    text = _text(csv_text)
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return [{_text(key): _text(value) for key, value in row.items() if _text(key)} for row in reader]


def csv_from_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    row_list = [dict(row) for row in rows or []]
    fieldnames: list[str] = []
    for row in row_list:
        for key in row:
            if str(key) not in fieldnames:
                fieldnames.append(str(key))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    if fieldnames:
        writer.writeheader()
        for row in row_list:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return output.getvalue()


def decimal_from_american(american_odds: Any) -> float | None:
    value = safe_float(american_odds)
    if value is None or value == 0:
        return None
    if value > 0:
        return round(1.0 + value / 100.0, 6)
    return round(1.0 + 100.0 / abs(value), 6)


def american_from_decimal(decimal_odds: Any) -> int | None:
    decimal_value = safe_float(decimal_odds)
    if decimal_value is None or decimal_value <= 1.0:
        return None
    if decimal_value >= 2.0:
        return int(round((decimal_value - 1.0) * 100.0))
    return int(round(-100.0 / (decimal_value - 1.0)))


def normalize_decimal_odds(row: Mapping[str, Any]) -> float | None:
    for key in ("decimal_odds", "decimal_price", "best_price", "odds_at_pick", "odds_decimal", "latest_value", "closing_value"):
        value = safe_float(row.get(key))
        if value is not None and value > 1.0:
            return round(value, 6)
    for key in ("american_odds", "american_price", "moneyline", "price_american"):
        value = decimal_from_american(row.get(key))
        if value is not None and value > 1.0:
            return round(value, 6)
    return None


def implied_probability(decimal_odds: Any) -> float | None:
    decimal_value = safe_float(decimal_odds)
    if decimal_value is None or decimal_value <= 1.0:
        return None
    return round(1.0 / decimal_value, 8)


def market_overround(decimal_odds_values: Sequence[Any]) -> float | None:
    probs = [implied_probability(value) for value in decimal_odds_values]
    valid = [value for value in probs if value is not None and value > 0]
    if not valid:
        return None
    return round(sum(valid), 8)


def no_vig_probabilities(decimal_odds_values: Sequence[Any]) -> list[float | None]:
    implied = [implied_probability(value) for value in decimal_odds_values]
    total = sum(value for value in implied if value is not None and value > 0)
    if total <= 0:
        return [None for _ in implied]
    return [None if value is None else round(value / total, 8) for value in implied]


def fair_decimal_odds(model_probability: Any) -> float | None:
    prob = normalize_probability(model_probability)
    if prob is None or prob <= 0:
        return None
    return round(1.0 / prob, 6)


def minimum_playable_decimal_odds(model_probability: Any, *, ev_buffer: float = 0.0, safety_margin: float = 0.0) -> float | None:
    prob = normalize_probability(model_probability)
    if prob is None or prob <= 0:
        return None
    required = (1.0 + float(ev_buffer or 0.0)) / prob
    return round(required + float(safety_margin or 0.0), 6)


def expected_value(model_probability: Any, decimal_odds: Any) -> float | None:
    prob = normalize_probability(model_probability)
    odds = safe_float(decimal_odds)
    if prob is None or odds is None or odds <= 1.0:
        return None
    return round(prob * odds - 1.0, 8)


def edge(model_probability: Any, market_probability: Any) -> float | None:
    prob = normalize_probability(model_probability)
    market = normalize_probability(market_probability)
    if prob is None or market is None:
        return None
    return round(prob - market, 8)


def fractional_kelly_stake_fraction(model_probability: Any, decimal_odds: Any, *, fraction: float = 0.25, cap: float = 0.03) -> float:
    prob = normalize_probability(model_probability)
    odds = safe_float(decimal_odds)
    if prob is None or odds is None or odds <= 1.0:
        return 0.0
    b = odds - 1.0
    q = 1.0 - prob
    full_kelly = ((b * prob) - q) / b if b > 0 else 0.0
    stake = max(0.0, full_kelly * float(fraction or 0.0))
    return round(min(stake, float(cap or 0.0)), 8)


def recommended_action(color: str, ev: float | None, stale: bool, unavailable: bool) -> str:
    if unavailable:
        return NO_BET
    if stale:
        return WAIT
    if color == GREEN and ev is not None and ev > 0:
        return PLAY
    if color == YELLOW:
        return WATCH
    return NO_BET


def _is_stale(row: Mapping[str, Any], max_age_minutes: int = 180) -> bool:
    status = " ".join(_text(row.get(key)).lower() for key in ("market_freshness_status", "odds_freshness_status", "edge_status", "odds_audit_status"))
    if "stale" in status or "expired" in status:
        return True
    timestamp = row.get("odds_timestamp") or row.get("price_timestamp") or row.get("prediction_timestamp")
    if not _text(timestamp):
        return False
    try:
        parsed = datetime.fromisoformat(_text(timestamp).replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).total_seconds() > max_age_minutes * 60


def _value_engine_row(source: Mapping[str, Any], decimal: float | None, model_probability: float | None) -> dict[str, Any]:
    row = dict(source or {})
    if decimal is not None:
        row["decimal_price"] = decimal
        row["odds_decimal"] = decimal
    if model_probability is not None:
        row.setdefault("model_probability", model_probability)
    return row


def assess_completed_odds_row(
    row: Mapping[str, Any],
    *,
    ev_buffer: float = 0.0,
    safety_margin: float = 0.02,
    kelly_fraction: float = 0.25,
    max_stake_fraction: float = 0.03,
    max_age_minutes: int = 180,
) -> dict[str, Any]:
    source = dict(row or {})
    decimal = normalize_decimal_odds(source)
    model_probability = None
    for key in ("model_probability", "final_probability", "adjusted_model_probability", "learned_model_probability", "probability", "confidence"):
        model_probability = normalize_probability(source.get(key))
        if model_probability is not None:
            break
    raw = implied_probability(decimal)
    fair = fair_decimal_odds(model_probability)
    min_playable = minimum_playable_decimal_odds(model_probability, ev_buffer=ev_buffer, safety_margin=safety_margin)
    ev = expected_value(model_probability, decimal)
    raw_edge = edge(model_probability, raw)
    base_assessment = assess_value_pick(_value_engine_row(source, decimal, model_probability), ev_buffer=ev_buffer, safety_margin=safety_margin, max_age_minutes=max_age_minutes)
    stale = _is_stale(source, max_age_minutes)
    unavailable = decimal is None or model_probability is None
    stake_fraction = fractional_kelly_stake_fraction(model_probability, decimal, fraction=kelly_fraction, cap=max_stake_fraction)
    action = recommended_action(base_assessment.color, ev, stale, unavailable)
    blockers: list[str] = []
    if decimal is None:
        blockers.append("missing_decimal_odds")
    if model_probability is None:
        blockers.append("missing_model_probability")
    if stale:
        blockers.append("stale_market")
    if ev is not None and ev <= ev_buffer:
        blockers.append("ev_below_buffer")
    if raw_edge is not None and raw_edge <= 0:
        blockers.append("edge_not_positive")
    return {
        "row_id": source.get("proof_id") or source.get("row_id") or source.get("id") or stable_hash("row", source, 12),
        "event": source.get("event") or source.get("event_name") or source.get("matchup") or "",
        "selection": source.get("selection") or source.get("pick") or source.get("prediction") or "",
        "sportsbook": source.get("sportsbook") or source.get("bookmaker") or source.get("book") or "",
        "decimal_odds": decimal,
        "american_odds": american_from_decimal(decimal),
        "model_probability": model_probability,
        "raw_implied_probability": raw,
        "edge": raw_edge,
        "expected_value": ev,
        "fair_odds": fair,
        "minimum_playable_odds": min_playable,
        "target_odds": base_assessment.target_odds,
        "kelly_fraction": stake_fraction,
        "stake_fraction": stake_fraction,
        "color": base_assessment.color,
        "recommendation": base_assessment.recommendation,
        "action": action,
        "reason": base_assessment.reason,
        "stale_market": stale,
        "market_unavailable": unavailable,
        "blockers": blockers,
        "rank_score": base_assessment.rank_score,
    }


def build_market_no_vig_report(market_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(row) for row in market_rows or []]
    odds = [normalize_decimal_odds(row) for row in rows]
    no_vig = no_vig_probabilities(odds)
    overround = market_overround(odds)
    output = []
    for index, row in enumerate(rows):
        decimal = odds[index]
        output.append({
            "row_index": index,
            "event": row.get("event") or row.get("event_name") or row.get("matchup") or "",
            "selection": row.get("selection") or row.get("outcome") or row.get("pick") or "",
            "decimal_odds": decimal,
            "american_odds": american_from_decimal(decimal),
            "raw_implied_probability": implied_probability(decimal),
            "no_vig_probability": no_vig[index],
        })
    margin = None if overround is None else round(overround - 1.0, 8)
    return {
        "market_side_count": len(rows),
        "overround": overround,
        "bookmaker_margin": margin,
        "no_vig_rows": output,
    }


def build_odds_math_completion_report(
    workspace_id: str | None = None,
    rows: Sequence[Mapping[str, Any]] | None = None,
    market_rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    ev_buffer: float = 0.0,
    safety_margin: float = 0.02,
    kelly_fraction: float = 0.25,
    max_stake_fraction: float = 0.03,
) -> dict[str, Any]:
    source_rows = [dict(row) for row in rows or []]
    assessed = [assess_completed_odds_row(row, ev_buffer=ev_buffer, safety_margin=safety_margin, kelly_fraction=kelly_fraction, max_stake_fraction=max_stake_fraction) for row in source_rows]
    market = build_market_no_vig_report(market_rows or source_rows)
    green = len([row for row in assessed if row["color"] == GREEN])
    yellow = len([row for row in assessed if row["color"] == YELLOW])
    red = len([row for row in assessed if row["color"] == RED])
    warning = len([row for row in assessed if row["color"] == DATA_WARNING])
    playable = len([row for row in assessed if row["action"] == PLAY])
    blocked = len([row for row in assessed if row["blockers"]])
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "odds_math_id": "",
        "row_count": len(source_rows),
        "green_count": green,
        "yellow_count": yellow,
        "red_count": red,
        "data_warning_count": warning,
        "playable_count": playable,
        "blocked_count": blocked,
        "ev_buffer": float(ev_buffer),
        "safety_margin": float(safety_margin),
        "kelly_fraction": float(kelly_fraction),
        "max_stake_fraction": float(max_stake_fraction),
        "market_no_vig": market,
        "odds_rows": assessed,
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": ["no playable value rows"] if source_rows and playable == 0 else [],
        "errors": [] if source_rows else ["no odds rows supplied"],
    }
    report["odds_math_id"] = stable_hash("odds_math", {"workspace_id": workspace_id, "rows": assessed}, 24)
    report["odds_math_hash"] = stable_hash("odds_math_hash", {k: v for k, v in report.items() if k != "generated_at_utc"}, 32)
    return report


def build_odds_math_completion_report_from_text(
    workspace_id: str | None = None,
    odds_csv_text: str | None = None,
    market_csv_text: str | None = None,
    *,
    ev_buffer: float = 0.0,
    safety_margin: float = 0.02,
    kelly_fraction: float = 0.25,
    max_stake_fraction: float = 0.03,
) -> dict[str, Any]:
    return build_odds_math_completion_report(
        workspace_id,
        parse_csv_text(odds_csv_text),
        parse_csv_text(market_csv_text),
        ev_buffer=ev_buffer,
        safety_margin=safety_margin,
        kelly_fraction=kelly_fraction,
        max_stake_fraction=max_stake_fraction,
    )


def export_odds_math_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_odds_rows_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("odds_rows") or [])
