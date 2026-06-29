from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.dashboard_data_service import DASHBOARD_FIELDS, build_dashboard_data
from autonomous_betting_agent.dashboard_ledger_bridge import dashboard_source_summary
from autonomous_betting_agent.ledger_import_review import (
    preview_ledger_import,
    review_correction_rows,
    review_duplicate_rows,
)
from autonomous_betting_agent.ledger_sync_service import SYNC_SOURCE_REGISTRY, sync_rows_by_source
from autonomous_betting_agent.performance_ledger_service import (
    export_performance_csv,
    export_performance_json,
    read_performance_ledger,
    read_recent_rows,
    rows_for_dashboard,
    summarize_performance,
    validate_ledger_integrity,
)


def _workspace(value: Any) -> str:
    text = str(value or "").strip().replace(" ", "_").lower()
    return text or "default"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _source_key(value: str) -> str:
    key = str(value or "").strip().lower()
    if key not in SYNC_SOURCE_REGISTRY:
        raise ValueError(f"Unsupported source_key: {value}")
    return key


def _as_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    return frame.to_dict(orient="records")


def _integrity_errors_by_type(errors: Sequence[str]) -> dict[str, list[str]]:
    duplicate_hash_errors: list[str] = []
    broken_chain_errors: list[str] = []
    row_hash_mismatch_errors: list[str] = []
    proof_id_warnings: list[str] = []
    other_errors: list[str] = []
    for error in errors or []:
        lowered = str(error).lower()
        if "duplicate row_hash" in lowered:
            duplicate_hash_errors.append(str(error))
        elif "previous_row_hash" in lowered or "broken" in lowered:
            broken_chain_errors.append(str(error))
        elif "row_hash mismatch" in lowered:
            row_hash_mismatch_errors.append(str(error))
        elif "proof_id" in lowered:
            proof_id_warnings.append(str(error))
        else:
            other_errors.append(str(error))
    return {
        "duplicate_hash_errors": duplicate_hash_errors,
        "broken_chain_errors": broken_chain_errors,
        "row_hash_mismatch_errors": row_hash_mismatch_errors,
        "proof_id_warnings": proof_id_warnings,
        "other_errors": other_errors,
    }


def get_ledger_health(workspace_id: str | None = None) -> dict[str, Any]:
    workspace = _workspace(workspace_id) if workspace_id else None
    integrity = validate_ledger_integrity(workspace_id=workspace)
    frame = read_performance_ledger(workspace_id=workspace)
    all_rows = read_performance_ledger()
    warnings = list(integrity.get("warnings", []) or [])
    errors = list(integrity.get("errors", []) or [])
    categorized = _integrity_errors_by_type(errors)
    missing_file_warnings = [warning for warning in warnings if "missing" in str(warning).lower() or "not found" in str(warning).lower()]
    malformed_file_warnings = [warning for warning in warnings if "malformed" in str(warning).lower() or "disagree" in str(warning).lower()]
    workspace_count = 0
    if not all_rows.empty and "workspace_id" in all_rows.columns:
        workspace_count = int(all_rows["workspace_id"].astype(str).nunique())
    last_sequence = 0
    last_row_hash = ""
    if not frame.empty:
        ordered = frame.copy(deep=True)
        ordered["_seq"] = pd.to_numeric(ordered.get("ledger_sequence", 0), errors="coerce").fillna(0)
        ordered = ordered.sort_values("_seq")
        last_sequence = int(ordered.iloc[-1]["_seq"])
        last_row_hash = str(ordered.iloc[-1].get("row_hash", ""))
    return {
        "status": integrity.get("status", "PASS"),
        "rows_checked": int(integrity.get("rows_checked", len(frame)) or 0),
        "schema_version": integrity.get("schema_version", ""),
        "missing_file_warnings": missing_file_warnings,
        "malformed_file_warnings": malformed_file_warnings,
        "duplicate_hash_errors": categorized["duplicate_hash_errors"],
        "broken_chain_errors": categorized["broken_chain_errors"],
        "row_hash_mismatch_errors": categorized["row_hash_mismatch_errors"],
        "proof_id_warnings": categorized["proof_id_warnings"],
        "workspace_count": workspace_count,
        "last_sequence": last_sequence,
        "last_row_hash": last_row_hash,
        "safe_to_append": integrity.get("status", "PASS") == "PASS",
        "warnings": warnings,
        "errors": errors + categorized["other_errors"],
    }


def get_dashboard_readiness(workspace_id: str | None = None) -> dict[str, Any]:
    workspace = _workspace(workspace_id) if workspace_id else None
    rows = rows_for_dashboard(workspace)
    source = dashboard_source_summary(workspace or "default")
    dashboard = build_dashboard_data(rows)
    missing_fields = [field for field in DASHBOARD_FIELDS if field not in dashboard]
    warnings = list(source.get("warnings", []) or [])
    if source.get("selected_source") != "ledger":
        warnings.append("Dashboard is not powered by durable ledger rows.")
    return {
        "workspace_id": workspace or "default",
        "dashboard_ready": bool(not rows.empty and not missing_fields and source.get("selected_source") == "ledger"),
        "dashboard_selected_source": source.get("selected_source"),
        "ledger_rows": int(source.get("ledger_rows", 0) or 0),
        "dashboard_rows": int(len(rows)),
        "fallback_source": source.get("selected_source") if source.get("selected_source") != "ledger" else "",
        "required_fields_present": not missing_fields,
        "missing_dashboard_fields": missing_fields,
        "dashboard": dashboard,
        "warnings": warnings,
        "errors": [],
    }


def get_proof_center_status(workspace_id: str | None = None) -> dict[str, Any]:
    workspace = _workspace(workspace_id) if workspace_id else None
    summary = summarize_performance(workspace_id=workspace)
    readiness = get_dashboard_readiness(workspace)
    health = get_ledger_health(workspace)
    return {
        "workspace_id": workspace or "default",
        "ledger_rows": int(summary.get("total_rows", 0) or 0),
        "dashboard_rows": int(readiness.get("dashboard_rows", 0) or 0),
        "unique_events": summary.get("unique_events", 0),
        "duplicate_count": summary.get("duplicate_count", 0),
        "correction_count": summary.get("correction_count", 0),
        "wins": summary.get("wins", 0),
        "losses": summary.get("losses", 0),
        "pushes": summary.get("pushes", 0),
        "cancels": summary.get("cancels", 0),
        "win_rate_ex_push_cancel": summary.get("win_rate_ex_push_cancel", 0.0),
        "profit_units": summary.get("profit_units", 0.0),
        "roi": summary.get("roi", 0.0),
        "average_clv": summary.get("average_clv"),
        "ledger_integrity_status": summary.get("ledger_integrity_status", health.get("status", "PASS")),
        "dashboard_selected_source": readiness.get("dashboard_selected_source"),
        "dashboard_ready": readiness.get("dashboard_ready", False),
        "last_updated_timestamp": summary.get("last_updated_timestamp", ""),
        "warnings": list(health.get("warnings", []) or []) + list(readiness.get("warnings", []) or []),
        "errors": list(health.get("errors", []) or []) + list(readiness.get("errors", []) or []),
    }


def approve_ledger_import(
    rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None,
    workspace_id: str,
    source_key: str,
    source_file: str | None = None,
    approval_reason: str | None = None,
) -> dict[str, Any]:
    workspace = _workspace(workspace_id)
    try:
        key = _source_key(source_key)
    except ValueError as exc:
        return {
            "approved": False,
            "approved_at_utc": "",
            "approval_reason": approval_reason or "",
            "blocked_reason": str(exc),
            "preview_hash": "",
            "write_attempted": False,
            "write_successful": False,
            "preview_result": {},
            "write_result": {},
            "warnings": [],
            "errors": [str(exc)],
        }
    preview = preview_ledger_import(rows, workspace, key, source_file=source_file)
    errors = list(preview.get("errors", []) or [])
    warnings = list(preview.get("warnings", []) or [])
    if errors:
        return {
            "approved": False,
            "approved_at_utc": "",
            "approval_reason": approval_reason or "",
            "blocked_reason": "preview has blocking errors",
            "preview_hash": preview.get("preview_hash", ""),
            "write_attempted": False,
            "write_successful": False,
            "preview_result": preview,
            "write_result": {},
            "warnings": warnings,
            "errors": errors,
        }
    if int(preview.get("rows_to_add", 0) or 0) <= 0:
        return {
            "approved": False,
            "approved_at_utc": "",
            "approval_reason": approval_reason or "",
            "blocked_reason": "no rows to add",
            "preview_hash": preview.get("preview_hash", ""),
            "write_attempted": False,
            "write_successful": False,
            "preview_result": preview,
            "write_result": {},
            "warnings": warnings,
            "errors": errors,
        }
    write_result = sync_rows_by_source(rows, workspace, key, source_file=source_file, dry_run=False)
    write_errors = list(write_result.get("errors", []) or [])
    preview_rows = int(preview.get("rows_to_add", 0) or 0)
    written_rows = int(write_result.get("rows_to_add", 0) or 0)
    write_successful = not write_errors and written_rows > 0 and written_rows <= preview_rows
    blocked_reason = ""
    if written_rows > preview_rows:
        write_errors.append("write result added more rows than approved preview")
        write_successful = False
        blocked_reason = "preview/write mismatch"
    elif written_rows != preview_rows:
        warnings.append("write result row count differed from approved preview")
    return {
        "approved": write_successful,
        "approved_at_utc": _utc_now() if write_successful else "",
        "approval_reason": approval_reason or "",
        "blocked_reason": blocked_reason,
        "preview_hash": preview.get("preview_hash", ""),
        "write_attempted": True,
        "write_successful": write_successful,
        "preview_result": preview,
        "write_result": write_result,
        "warnings": warnings + list(write_result.get("warnings", []) or []),
        "errors": write_errors,
    }


def get_public_proof_exports(workspace_id: str | None = None) -> dict[str, str]:
    workspace = _workspace(workspace_id) if workspace_id else None
    return {
        "csv": export_performance_csv(workspace_id=workspace, public_safe=True),
        "json": export_performance_json(workspace_id=workspace, public_safe=True),
    }


def get_private_proof_exports(workspace_id: str | None = None) -> dict[str, str]:
    workspace = _workspace(workspace_id) if workspace_id else None
    return {
        "csv": export_performance_csv(workspace_id=workspace, public_safe=False),
        "json": export_performance_json(workspace_id=workspace, public_safe=False),
    }


def get_recent_proof_rows(workspace_id: str | None = None, limit: int = 100) -> pd.DataFrame:
    workspace = _workspace(workspace_id) if workspace_id else None
    return read_recent_rows(workspace_id=workspace, limit=limit)


def get_proof_center_summary(workspace_id: str | None = None) -> dict[str, Any]:
    return get_proof_center_status(workspace_id=workspace_id)


# Re-export with the requested public function names from this service layer.
preview_ledger_import = preview_ledger_import
review_duplicate_rows = review_duplicate_rows
review_correction_rows = review_correction_rows
