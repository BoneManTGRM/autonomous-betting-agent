import csv
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.profitability_metrics import (
    clv,
    decimal_odds,
    edge,
    expected_value,
    lane,
    no_vig_edge,
    odds_verified,
    probability,
    profit_units,
    result_status,
    stake_units,
    text,
    truthy,
)

SCHEMA_VERSION = "3E.9.0"
REPO_ROOT = Path(__file__).resolve().parents[1]
LEDGER_CSV_PATH = REPO_ROOT / "data" / "proof_performance_ledger.csv"
LEDGER_JSON_PATH = REPO_ROOT / "data" / "proof_performance_ledger.json"
BACKUP_DIR = REPO_ROOT / "data" / "ledger_backups"

SCHEMA_FIELDS = [
    "schema_version",
    "proof_id",
    "workspace_id",
    "ledger_sequence",
    "record_type",
    "created_at_utc",
    "ingested_at_utc",
    "locked_at_utc",
    "event",
    "sport",
    "league",
    "market_type",
    "pick",
    "sportsbook",
    "decimal_odds",
    "model_probability",
    "raw_implied_probability",
    "no_vig_implied_probability",
    "edge",
    "no_vig_edge",
    "expected_value",
    "clv",
    "stake_units",
    "result",
    "profit_units",
    "report_lane",
    "official_publish_ready",
    "odds_verified",
    "source_key",
    "source_file",
    "duplicate_key",
    "row_hash",
    "previous_row_hash",
    "corrected_from_proof_id",
    "correction_reason",
]

PUBLIC_SAFE_FIELDS = [
    "proof_id",
    "workspace_id",
    "created_at_utc",
    "locked_at_utc",
    "event",
    "sport",
    "league",
    "market_type",
    "pick",
    "sportsbook",
    "decimal_odds",
    "model_probability",
    "raw_implied_probability",
    "no_vig_implied_probability",
    "edge",
    "no_vig_edge",
    "expected_value",
    "clv",
    "stake_units",
    "result",
    "profit_units",
    "report_lane",
    "odds_verified",
    "duplicate_key",
    "row_hash",
]

HASH_FIELDS = [
    "schema_version",
    "workspace_id",
    "record_type",
    "locked_at_utc",
    "event",
    "sport",
    "league",
    "market_type",
    "pick",
    "sportsbook",
    "decimal_odds",
    "model_probability",
    "raw_implied_probability",
    "no_vig_implied_probability",
    "edge",
    "no_vig_edge",
    "expected_value",
    "clv",
    "stake_units",
    "result",
    "profit_units",
    "report_lane",
    "official_publish_ready",
    "odds_verified",
    "source_key",
    "duplicate_key",
    "corrected_from_proof_id",
    "correction_reason",
]

ALIAS_MAP = {
    "event": ("event", "public_event", "event_name", "matchup", "game", "fixture"),
    "pick": ("pick", "prediction", "public_pick", "selection", "bet_selection"),
    "sportsbook": ("sportsbook", "bookmaker", "book", "odds_source", "source"),
    "market_type": ("market_type", "market", "market_name", "bet_type"),
    "decimal_odds": ("decimal_odds", "decimal_price", "best_price", "average_price", "avg_price", "odds_decimal", "odds_at_pick", "odds"),
    "edge": ("edge", "model_market_edge", "raw_edge", "current_edge"),
    "no_vig_edge": ("no_vig_edge", "model_no_vig_edge", "novig_edge"),
    "expected_value": ("expected_value", "expected_value_per_unit", "ev", "value_ev"),
    "clv": ("clv", "manual_clv", "manual_clv_value", "clv_delta", "closing_line_value"),
    "result": ("result", "grade", "outcome", "pick_result", "result_status"),
    "model_probability": ("model_probability", "learned_model_probability", "final_adjusted_probability", "adjusted_model_probability", "probability", "confidence"),
    "raw_implied_probability": ("raw_implied_probability", "market_probability", "implied_probability"),
    "no_vig_implied_probability": ("no_vig_implied_probability", "no_vig_market_probability"),
    "sport": ("sport", "sport_key"),
    "league": ("league", "competition"),
    "locked_at_utc": ("locked_at_utc", "locked_at", "pick_locked_at", "odds_locked_at"),
    "created_at_utc": ("created_at_utc", "created_at", "generated_at", "timestamp"),
    "stake_units": ("stake_units", "risk_units", "units", "stake"),
    "profit_units": ("profit_units", "profit", "net_units"),
    "report_lane": ("report_lane", "report_lane_v2", "lane", "official_status_label"),
    "official_publish_ready": ("official_publish_ready", "publish_ready", "client_report_ready"),
    "odds_verified": ("odds_verified", "verified_odds", "market_verified"),
    "source_key": ("source_key", "source_context"),
    "source_file": ("source_file", "filename", "file_name"),
    "proof_id": ("proof_id", "public_proof_id", "lock_id"),
    "record_type": ("record_type", "ledger_record_type"),
    "corrected_from_proof_id": ("corrected_from_proof_id", "correction_of", "original_proof_id"),
    "correction_reason": ("correction_reason", "correction_note", "audit_reason"),
}

VALID_RECORD_TYPES = {"original", "import", "generated", "manual_review", "correction", "system_summary"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _first(row: Mapping[str, Any], target: str) -> Any:
    for key in ALIAS_MAP.get(target, (target,)):
        if key in row and text(row.get(key)):
            return row.get(key)
    return ""


def _clean_workspace(value: Any) -> str:
    cleaned = text(value).strip().replace(" ", "_").lower()
    return cleaned or "default"


def _number_value(value: Any) -> float | None:
    raw = text(value)
    if not raw:
        return None
    try:
        return float(raw.replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def _prob_value(value: Any) -> float | None:
    return probability(value)


def _bool_value(value: Any) -> bool:
    return truthy(value)


def _canonical_json(payload: Mapping[str, Any], fields: Sequence[str]) -> str:
    stable = {field: _json_value(payload.get(field)) for field in fields}
    return json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _json_value(value: Any) -> Any:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return round(float(value), 10)
    return str(value).strip()


def _sha(prefix: str, payload: str, length: int = 20) -> str:
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:length]
    return f"{prefix}_{digest}"


def _hash_payload(row: Mapping[str, Any]) -> str:
    return _canonical_json(row, HASH_FIELDS)


def build_duplicate_key(row: Mapping[str, Any]) -> str:
    workspace_id = _clean_workspace(row.get("workspace_id"))
    parts = [
        workspace_id,
        text(row.get("event")).lower(),
        text(row.get("market_type")).lower(),
        text(row.get("pick")).lower(),
        text(row.get("sportsbook")).lower(),
        text(row.get("locked_at_utc")).lower(),
    ]
    return _sha("dup", "|".join(parts), length=24)


def build_row_hash(row: Mapping[str, Any]) -> str:
    return _sha("row", _hash_payload(row), length=32)


def build_proof_id(row: Mapping[str, Any]) -> str:
    existing = text(row.get("proof_id"))
    if existing:
        return existing
    seed = "|".join(
        [
            _clean_workspace(row.get("workspace_id")),
            text(row.get("record_type")) or "original",
            text(row.get("duplicate_key")),
            text(row.get("locked_at_utc")),
            build_row_hash(row),
            text(row.get("corrected_from_proof_id")),
            text(row.get("correction_reason")),
        ]
    )
    return _sha("proof", seed, length=24)


def normalize_performance_record(row: Mapping[str, Any], workspace_id: str, source_key: str | None = None, source_file: str | None = None) -> dict[str, Any]:
    raw = dict(row or {})
    normalized: dict[str, Any] = {field: "" for field in SCHEMA_FIELDS}
    normalized["schema_version"] = text(raw.get("schema_version")) or SCHEMA_VERSION
    normalized["workspace_id"] = _clean_workspace(raw.get("workspace_id") or workspace_id)
    record_type = text(_first(raw, "record_type")) or ("correction" if text(_first(raw, "corrected_from_proof_id")) else "import" if source_key else "original")
    normalized["record_type"] = record_type if record_type in VALID_RECORD_TYPES else "import"
    normalized["created_at_utc"] = text(_first(raw, "created_at_utc")) or utc_now()
    normalized["ingested_at_utc"] = text(raw.get("ingested_at_utc")) or utc_now()
    normalized["locked_at_utc"] = text(_first(raw, "locked_at_utc"))
    normalized["event"] = text(_first(raw, "event"))
    normalized["sport"] = text(_first(raw, "sport"))
    normalized["league"] = text(_first(raw, "league"))
    normalized["market_type"] = text(_first(raw, "market_type"))
    normalized["pick"] = text(_first(raw, "pick"))
    normalized["sportsbook"] = text(_first(raw, "sportsbook"))

    odds = decimal_odds(raw)
    normalized["decimal_odds"] = odds if odds is not None else _number_value(_first(raw, "decimal_odds"))
    normalized["model_probability"] = _prob_value(_first(raw, "model_probability"))
    normalized["raw_implied_probability"] = _prob_value(_first(raw, "raw_implied_probability"))
    if normalized["raw_implied_probability"] in (None, "") and normalized["decimal_odds"]:
        normalized["raw_implied_probability"] = round(1.0 / float(normalized["decimal_odds"]), 10)
    normalized["no_vig_implied_probability"] = _prob_value(_first(raw, "no_vig_implied_probability"))
    normalized["edge"] = edge(raw)
    if normalized["edge"] is None and normalized["model_probability"] not in (None, "") and normalized["raw_implied_probability"] not in (None, ""):
        normalized["edge"] = round(float(normalized["model_probability"]) - float(normalized["raw_implied_probability"]), 10)
    normalized["no_vig_edge"] = no_vig_edge(raw)
    if normalized["no_vig_edge"] is None and normalized["model_probability"] not in (None, "") and normalized["no_vig_implied_probability"] not in (None, ""):
        normalized["no_vig_edge"] = round(float(normalized["model_probability"]) - float(normalized["no_vig_implied_probability"]), 10)
    normalized["expected_value"] = expected_value(raw)
    normalized["clv"] = clv(raw)
    normalized["stake_units"] = stake_units(raw)
    normalized["result"] = result_status(raw)
    normalized["profit_units"] = profit_units(raw)
    normalized["report_lane"] = text(_first(raw, "report_lane")) or lane(raw)
    normalized["official_publish_ready"] = _bool_value(_first(raw, "official_publish_ready"))
    normalized["odds_verified"] = _bool_value(_first(raw, "odds_verified")) or odds_verified(raw)
    normalized["source_key"] = text(source_key) or text(_first(raw, "source_key"))
    normalized["source_file"] = text(source_file) or text(_first(raw, "source_file"))
    normalized["corrected_from_proof_id"] = text(_first(raw, "corrected_from_proof_id"))
    normalized["correction_reason"] = text(_first(raw, "correction_reason"))
    normalized["duplicate_key"] = text(raw.get("duplicate_key")) or build_duplicate_key(normalized)
    normalized["proof_id"] = text(_first(raw, "proof_id")) or build_proof_id(normalized)
    normalized["row_hash"] = text(raw.get("row_hash")) or build_row_hash(normalized)
    normalized["previous_row_hash"] = text(raw.get("previous_row_hash"))
    sequence = _number_value(raw.get("ledger_sequence"))
    normalized["ledger_sequence"] = int(sequence) if sequence is not None else 0
    return normalized


def _records_to_frame(records: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=SCHEMA_FIELDS)
    frame = pd.DataFrame([dict(record) for record in records])
    for field in SCHEMA_FIELDS:
        if field not in frame.columns:
            frame[field] = ""
    return frame[SCHEMA_FIELDS]


def _frame_to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        record = {}
        for field in SCHEMA_FIELDS:
            value = row.get(field, "")
            try:
                if pd.isna(value):
                    value = ""
            except (TypeError, ValueError):
                pass
            record[field] = value
        records.append(record)
    return records


def _read_json_file(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if not path.exists():
        return [], warnings
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload.get("rows", payload) if isinstance(payload, dict) else payload
        if not isinstance(records, list):
            return [], [f"Malformed JSON ledger: {path}"]
        return [normalize_performance_record(record, text(record.get("workspace_id")) or "default") for record in records if isinstance(record, Mapping)], warnings
    except Exception as exc:
        return [], [f"Malformed JSON ledger: {exc}"]


def _read_csv_file(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not path.exists():
        return [], []
    try:
        frame = pd.read_csv(path)
        return [normalize_performance_record(row.to_dict(), text(row.get("workspace_id")) or "default") for _, row in frame.iterrows()], []
    except Exception as exc:
        return [], [f"Malformed CSV ledger: {exc}"]


def _max_sequence(records: Sequence[Mapping[str, Any]]) -> int:
    values = []
    for record in records:
        try:
            values.append(int(float(record.get("ledger_sequence") or 0)))
        except (TypeError, ValueError):
            values.append(0)
    return max(values) if values else 0


def _last_hash(records: Sequence[Mapping[str, Any]]) -> str:
    if not records:
        return ""
    ordered = sorted(records, key=lambda record: int(float(record.get("ledger_sequence") or 0)))
    return text(ordered[-1].get("row_hash"))


def _select_records(json_records: list[dict[str, Any]], csv_records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    if json_records and csv_records:
        if len(json_records) != len(csv_records) or _max_sequence(json_records) != _max_sequence(csv_records):
            warnings.append("CSV and JSON ledgers disagree; selected highest sequence ledger.")
        return (json_records if _max_sequence(json_records) >= _max_sequence(csv_records) else csv_records), warnings
    if json_records:
        return json_records, warnings
    if csv_records:
        return csv_records, warnings
    return [], warnings


def _backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR / f"{path.name}.{stamp}.bak"


def _write_json_records(records: Sequence[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": SCHEMA_VERSION, "rows": [dict(record) for record in records]}
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent), suffix=".tmp") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        temp_path = Path(handle.name)
    json.loads(temp_path.read_text(encoding="utf-8"))
    if path.exists():
        shutil.copy2(path, _backup_path(path))
    os.replace(temp_path, path)


def _write_csv_records(records: Sequence[Mapping[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False, dir=str(path.parent), suffix=".tmp") as handle:
        writer = csv.DictWriter(handle, fieldnames=SCHEMA_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in SCHEMA_FIELDS})
        temp_path = Path(handle.name)
    pd.read_csv(temp_path)
    if path.exists():
        shutil.copy2(path, _backup_path(path))
    os.replace(temp_path, path)


def _persist_records(records: Sequence[Mapping[str, Any]]) -> None:
    _write_csv_records(records, LEDGER_CSV_PATH)
    _write_json_records(records, LEDGER_JSON_PATH)


def read_performance_ledger(workspace_id: str | None = None) -> pd.DataFrame:
    json_records, _json_warnings = _read_json_file(LEDGER_JSON_PATH)
    csv_records, _csv_warnings = _read_csv_file(LEDGER_CSV_PATH)
    records, _warnings = _select_records(json_records, csv_records)
    if records and LEDGER_JSON_PATH.exists() and not LEDGER_CSV_PATH.exists():
        _write_csv_records(records, LEDGER_CSV_PATH)
    if records and LEDGER_CSV_PATH.exists() and not LEDGER_JSON_PATH.exists():
        _write_json_records(records, LEDGER_JSON_PATH)
    if workspace_id:
        workspace = _clean_workspace(workspace_id)
        records = [record for record in records if _clean_workspace(record.get("workspace_id")) == workspace]
    return _records_to_frame(records)


def _reject_reason(record: Mapping[str, Any]) -> str:
    if not text(record.get("workspace_id")):
        return "missing workspace_id"
    if not text(record.get("event")) and not text(record.get("pick")) and record.get("record_type") != "system_summary":
        return "missing event and pick"
    if record.get("record_type") == "correction" and (not text(record.get("corrected_from_proof_id")) or not text(record.get("correction_reason"))):
        return "correction rows require corrected_from_proof_id and correction_reason"
    return ""


def _ingestion_summary(rows: Sequence[Mapping[str, Any]], duplicate_count: int, rejected_count: int) -> dict[str, Any]:
    return {
        "rows_seen": len(rows),
        "rows_to_add": len(rows) - duplicate_count - rejected_count,
        "duplicates_detected": duplicate_count,
        "rejected_rows": rejected_count,
    }


def append_performance_rows(
    rows: pd.DataFrame | Sequence[Mapping[str, Any]],
    workspace_id: str,
    source_key: str | None = None,
    source_file: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    incoming_frame = rows.copy(deep=True) if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows or []))
    incoming_rows = [series.to_dict() for _, series in incoming_frame.iterrows()] if not incoming_frame.empty else []
    existing_records = _frame_to_records(read_performance_ledger())
    existing_proof_ids = {text(record.get("proof_id")) for record in existing_records if text(record.get("proof_id"))}
    existing_duplicate_keys = {text(record.get("duplicate_key")) for record in existing_records if text(record.get("duplicate_key"))}
    incoming_proof_ids: set[str] = set()
    incoming_duplicate_keys: set[str] = set()
    duplicates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    additions: list[dict[str, Any]] = []
    next_sequence = _max_sequence(existing_records) + 1
    previous_hash = _last_hash(existing_records)

    for raw in incoming_rows:
        record = normalize_performance_record(raw, workspace_id, source_key=source_key, source_file=source_file)
        reason = _reject_reason(record)
        if reason:
            rejected.append({"reason": reason, "row": record})
            continue
        proof_id = text(record.get("proof_id"))
        duplicate_key = text(record.get("duplicate_key"))
        is_correction = record.get("record_type") == "correction"
        if proof_id in existing_proof_ids or proof_id in incoming_proof_ids:
            duplicates.append(record)
            continue
        if duplicate_key and not is_correction and (duplicate_key in existing_duplicate_keys or duplicate_key in incoming_duplicate_keys):
            duplicates.append(record)
            continue
        record["ledger_sequence"] = next_sequence
        record["previous_row_hash"] = previous_hash
        record["row_hash"] = build_row_hash(record)
        previous_hash = text(record.get("row_hash"))
        next_sequence += 1
        incoming_proof_ids.add(proof_id)
        if duplicate_key:
            incoming_duplicate_keys.add(duplicate_key)
        additions.append(record)

    result = {
        "rows_seen": len(incoming_rows),
        "rows_to_add": len(additions),
        "duplicates_detected": len(duplicates),
        "rejected_rows": len(rejected),
        "correction_rows_detected": sum(1 for row in additions if row.get("record_type") == "correction"),
        "warnings": warnings,
        "errors": errors,
        "summary": _ingestion_summary(incoming_rows, len(duplicates), len(rejected)),
        "added_rows": additions,
        "duplicate_rows": duplicates,
        "rejected_row_details": rejected,
        "dry_run": bool(dry_run),
    }
    if dry_run or not additions:
        return result
    _persist_records(existing_records + additions)
    return result


def read_workspace_rows(workspace_id: str) -> pd.DataFrame:
    return read_performance_ledger(workspace_id=workspace_id)


def read_recent_rows(workspace_id: str | None = None, limit: int = 100) -> pd.DataFrame:
    frame = read_performance_ledger(workspace_id=workspace_id)
    if frame.empty:
        return frame
    ordered = frame.copy(deep=True)
    ordered["_seq"] = pd.to_numeric(ordered["ledger_sequence"], errors="coerce").fillna(0)
    ordered = ordered.sort_values("_seq", ascending=False).drop(columns=["_seq"])
    return ordered.head(limit).reset_index(drop=True)


def _export_frame(workspace_id: str | None = None, public_safe: bool = False) -> pd.DataFrame:
    frame = read_performance_ledger(workspace_id=workspace_id)
    if public_safe:
        for field in PUBLIC_SAFE_FIELDS:
            if field not in frame.columns:
                frame[field] = ""
        return frame[PUBLIC_SAFE_FIELDS]
    return frame


def export_performance_csv(workspace_id: str | None = None, public_safe: bool = False) -> str:
    return _export_frame(workspace_id=workspace_id, public_safe=public_safe).to_csv(index=False)


def export_performance_json(workspace_id: str | None = None, public_safe: bool = False) -> str:
    frame = _export_frame(workspace_id=workspace_id, public_safe=public_safe)
    records = _frame_to_records(frame) if not public_safe else frame.to_dict(orient="records")
    return json.dumps({"schema_version": SCHEMA_VERSION, "rows": records}, indent=2, sort_keys=True)


def validate_ledger_integrity(workspace_id: str | None = None) -> dict[str, Any]:
    json_records, json_warnings = _read_json_file(LEDGER_JSON_PATH)
    csv_records, csv_warnings = _read_csv_file(LEDGER_CSV_PATH)
    records, select_warnings = _select_records(json_records, csv_records)
    if workspace_id:
        workspace = _clean_workspace(workspace_id)
        records = [record for record in records if _clean_workspace(record.get("workspace_id")) == workspace]
    warnings = json_warnings + csv_warnings + select_warnings
    errors: list[str] = []
    previous = ""
    seen_sequences: set[int] = set()
    seen_hashes: set[str] = set()
    for record in sorted(records, key=lambda item: int(float(item.get("ledger_sequence") or 0))):
        if not text(record.get("schema_version")):
            errors.append("missing schema_version")
        try:
            sequence = int(float(record.get("ledger_sequence") or 0))
        except (TypeError, ValueError):
            errors.append("invalid ledger_sequence")
            sequence = 0
        if sequence in seen_sequences and sequence != 0:
            errors.append(f"duplicate ledger_sequence:{sequence}")
        seen_sequences.add(sequence)
        row_hash = text(record.get("row_hash"))
        if not row_hash:
            errors.append("missing row_hash")
        if row_hash in seen_hashes:
            errors.append(f"duplicate row_hash:{row_hash}")
        seen_hashes.add(row_hash)
        if text(record.get("previous_row_hash")) != previous and sequence > 1:
            errors.append(f"broken previous_row_hash at sequence {sequence}")
        if row_hash and row_hash != build_row_hash(record):
            errors.append(f"row_hash mismatch at sequence {sequence}")
        previous = row_hash
    return {
        "status": "PASS" if not errors else "FAIL",
        "rows_checked": len(records),
        "warnings": warnings,
        "errors": errors,
        "schema_version": SCHEMA_VERSION,
    }
