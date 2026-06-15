from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

FIELD_GROUPS: dict[str, tuple[str, ...]] = {
    "prediction_timestamp": ("prediction_timestamp", "predicted_at", "pick_timestamp", "created_at", "generated_at_utc", "prediction_generated_at"),
    "event_start_time": ("event_start_time", "event_start", "start_time", "start", "commence_time", "game_time", "date"),
    "odds_at_prediction": ("sportsbook_odds", "best_price", "entry_price", "entry_odds", "decimal_odds", "odds", "price"),
    "odds_snapshot_timestamp": ("odds_snapshot_timestamp", "odds_timestamp", "odds_captured_at", "price_timestamp", "market_timestamp"),
    "final_result": ("actual_winner", "winner", "winning_side", "final_winner", "final_score", "score"),
    "win_loss": ("result", "outcome", "win_loss", "graded_result", "status"),
    "profit_loss": ("profit_loss", "p_l", "pl", "units_profit_loss", "unit_profit_loss"),
    "roi_or_return_metric": ("roi", "return_on_investment", "unit_roi"),
    "confidence_score": ("confidence", "confidence_score", "confidence_bucket", "calibrated_probability", "model_probability", "predictor_score", "final_probability"),
    "calibration_score": ("calibration_score", "calibration_gap", "brier_score", "log_loss", "calibrated_probability", "adjusted_probability"),
    "sport_or_league": ("sport", "league", "competition", "sport_group"),
    "market_or_pick_type": ("market", "market_key", "prop_type", "bet_type"),
    "api_inputs_used": ("api_inputs_used", "api_inputs", "provider_inputs", "input_sources", "source_payloads"),
    "data_sources_used": ("data_sources_used", "data_sources", "source", "sources", "books", "bookmaker_count", "provider"),
    "immutable_record_id": ("immutable_record_id", "record_hash", "audit_hash", "row_hash", "source_game_id", "game_id", "event_id", "sdio_game_id", "sportsdataio_game_id"),
    "edit_lock_or_no_manual_edit_proof": ("edit_lock_status", "locked_at", "prediction_locked_at", "audit_lock", "no_manual_edit_after_start", "source_commit_sha", "record_hash"),
}

SALE_GRADE_REQUIRED = (
    "prediction_timestamp",
    "event_start_time",
    "odds_at_prediction",
    "odds_snapshot_timestamp",
    "final_result",
    "win_loss",
    "profit_loss",
    "confidence_score",
    "calibration_score",
    "sport_or_league",
    "api_inputs_used",
    "data_sources_used",
    "immutable_record_id",
    "edit_lock_or_no_manual_edit_proof",
)

PROOF_METRICS_INCLUDED = (
    "timestamped_predictions",
    "odds_at_prediction_time",
    "final_result",
    "win_loss",
    "profit_loss_units",
    "roi_support",
    "confidence_score",
    "calibration_score",
    "sport_or_league_breakdown_support",
    "api_inputs_used",
    "data_sources_used",
    "duplicate_padding_check_support",
    "record_hash_or_lock_support",
    "no_manual_edit_after_start_support",
)


def attach_proof_audit(payload: Mapping[str, Any], rows: Sequence[Any] | Iterable[Any], *, report_name: str) -> dict[str, Any]:
    output = dict(payload)
    output["proof_audit"] = build_report_proof(rows, report_name=report_name)
    return output


def build_report_proof(rows: Sequence[Any] | Iterable[Any], *, report_name: str) -> dict[str, Any]:
    normalized_rows = [_to_mapping(row) for row in rows]
    coverage = {name: _coverage(normalized_rows, columns) for name, columns in FIELD_GROUPS.items()}
    duplicates = _duplicate_summary(normalized_rows)
    missing_critical = [name for name in SALE_GRADE_REQUIRED if coverage[name]["present_rows"] == 0]
    partial_critical = [name for name in SALE_GRADE_REQUIRED if 0 < coverage[name]["coverage"] < 0.95]

    if missing_critical:
        status = "NEEDS_PROOF_FIELDS"
    elif partial_critical or duplicates["duplicate_candidate_rows"] > 0:
        status = "PARTIAL_PROOF_ONLY"
    else:
        status = "SALE_GRADE_READY"

    required_actions: list[str] = []
    if "prediction_timestamp" in missing_critical:
        required_actions.append("Add a prediction timestamp before each game starts.")
    if "odds_snapshot_timestamp" in missing_critical:
        required_actions.append("Store the odds snapshot timestamp used for each pick.")
    if "odds_at_prediction" in missing_critical:
        required_actions.append("Store entry odds or best price at prediction time.")
    if "profit_loss" in missing_critical:
        required_actions.append("Add per-pick unit profit/loss so ROI can be verified.")
    if "api_inputs_used" in missing_critical or "data_sources_used" in missing_critical:
        required_actions.append("Record which APIs, books, feeds, and model inputs were used for each prediction.")
    if "edit_lock_or_no_manual_edit_proof" in missing_critical:
        required_actions.append("Add immutable record hashes, lock timestamps, or commit-backed proof that picks were not manually edited after game start.")
    if partial_critical:
        required_actions.append("Increase partially populated proof fields to at least 95 percent row coverage.")
    if duplicates["duplicate_candidate_rows"] > 0:
        required_actions.append("Remove or explain duplicate event/market/pick rows before using the report in a sales claim.")

    return {
        "report_name": report_name,
        "proof_standard": "commercial_sale_grade_v1",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_status": status,
        "rows_reviewed": len(normalized_rows),
        "metrics_added_to_report_family": list(PROOF_METRICS_INCLUDED),
        "field_coverage": coverage,
        "missing_critical_fields": missing_critical,
        "partial_critical_fields": partial_critical,
        "duplicate_summary": duplicates,
        "row_hash_sample": [_stable_hash(row) for row in normalized_rows[:10]],
        "required_actions": required_actions,
        "buyer_due_diligence_notes": [
            "A high win rate is not proof of profitability unless entry odds, closing odds, ROI, and duplicates are verified.",
            "The strongest sales evidence is prospectively timestamped picks with immutable hashes and odds captured before event start.",
            "Reports should be treated as research outputs, not betting instructions or guaranteed returns.",
        ],
    }


def _coverage(rows: Sequence[Mapping[str, Any]], columns: tuple[str, ...]) -> dict[str, Any]:
    present = 0
    matched_columns: set[str] = set()
    for row in rows:
        match = _first_match(row, columns)
        if match is not None:
            present += 1
            matched_columns.add(match)
    total = len(rows)
    return {
        "accepted_columns": list(columns),
        "matched_columns": sorted(matched_columns),
        "present_rows": present,
        "missing_rows": total - present,
        "coverage": 0.0 if total == 0 else round(present / total, 4),
    }


def _duplicate_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    seen: set[tuple[str, str, str, str, str]] = set()
    duplicate_rows = 0
    for row in rows:
        key = (
            str(_first_value(row, ("source_game_id", "game_id", "event_id", "sdio_game_id", "sportsdataio_game_id")) or "").strip().lower(),
            str(_first_value(row, ("event_name", "event", "game", "match", "fixture")) or "").strip().lower(),
            str(_first_value(row, ("event_start_time", "event_start", "start_time", "start", "commence_time", "date")) or "").strip().lower(),
            str(_first_value(row, ("market", "market_key", "prop_type", "bet_type")) or "").strip().lower(),
            str(_first_value(row, ("predicted_winner", "prediction", "pick", "selection", "team", "player_name")) or "").strip().lower(),
        )
        if not any(key):
            continue
        if key in seen:
            duplicate_rows += 1
        else:
            seen.add(key)
    return {
        "unique_candidate_keys": len(seen),
        "duplicate_candidate_rows": duplicate_rows,
        "key_fields": ["game_id/event", "event_start", "market", "pick"],
    }


def _first_match(row: Mapping[str, Any], columns: tuple[str, ...]) -> str | None:
    lookup = {_clean_key(str(key)): value for key, value in row.items()}
    for column in columns:
        value = lookup.get(_clean_key(column))
        if value not in (None, ""):
            return column
    return None


def _first_value(row: Mapping[str, Any], columns: tuple[str, ...]) -> Any:
    lookup = {_clean_key(str(key)): value for key, value in row.items()}
    for column in columns:
        value = lookup.get(_clean_key(column))
        if value not in (None, ""):
            return value
    return None


def _to_mapping(row: Any) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    if hasattr(row, "to_dict"):
        return dict(row.to_dict())
    if is_dataclass(row):
        return dict(asdict(row))
    if hasattr(row, "__dict__"):
        return dict(vars(row))
    return {"value": str(row)}


def _stable_hash(row: Mapping[str, Any]) -> str:
    clean = {_clean_key(str(key)): _json_safe(value) for key, value in row.items() if value not in (None, "")}
    payload = json.dumps(clean, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clean_key(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return str(value)
