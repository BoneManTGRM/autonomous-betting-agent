from typing import Any, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.performance_ledger_service import append_performance_rows

ODDS_LOCK_SOURCE = "odds_lock"
PRO_PREDICTOR_SOURCE = "pro_predictor"
REPORT_STUDIO_SOURCE = "report_studio"
PROOF_CENTER_SOURCE = "proof_center"
LEARNING_PAGE_SOURCE = "learning_page"
UPLOADED_CSV_SOURCE = "uploaded_csv"
GENERATED_PICK_SOURCE = "generated_pick"
MANUAL_REVIEW_SOURCE = "manual_review"

SYNC_SOURCE_REGISTRY = {
    ODDS_LOCK_SOURCE: "Odds Lock Pro rows",
    PRO_PREDICTOR_SOURCE: "Pro Predictor rows",
    REPORT_STUDIO_SOURCE: "Report Studio rows",
    PROOF_CENTER_SOURCE: "Proof Center rows",
    LEARNING_PAGE_SOURCE: "Learning page rows",
    UPLOADED_CSV_SOURCE: "Uploaded CSV rows",
    GENERATED_PICK_SOURCE: "Generated pick rows",
    MANUAL_REVIEW_SOURCE: "Manual review rows",
}

SYNC_RESULT_KEYS = (
    "source_key",
    "workspace_id",
    "dry_run",
    "rows_seen",
    "rows_to_add",
    "duplicates_detected",
    "rejected_rows",
    "correction_rows_detected",
    "warnings",
    "errors",
    "summary",
    "added_rows",
    "duplicate_rows",
    "rejected_row_details",
)


def _workspace(value: Any) -> str:
    text = str(value or "").strip().replace(" ", "_").lower()
    return text or "default"


def _rows_frame(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None) -> pd.DataFrame:
    if rows is None:
        return pd.DataFrame()
    if isinstance(rows, pd.DataFrame):
        return rows.copy(deep=True)
    return pd.DataFrame([dict(row) for row in rows])


def _normal_source_key(source_key: str) -> str:
    key = str(source_key or "").strip().lower()
    if key not in SYNC_SOURCE_REGISTRY:
        raise ValueError(f"Unsupported source_key: {source_key}")
    return key


def _stable_result(source_key: str, workspace_id: str, dry_run: bool, raw_result: Mapping[str, Any]) -> dict[str, Any]:
    result = {
        "source_key": source_key,
        "workspace_id": _workspace(workspace_id),
        "dry_run": bool(dry_run),
        "rows_seen": int(raw_result.get("rows_seen", 0) or 0),
        "rows_to_add": int(raw_result.get("rows_to_add", 0) or 0),
        "duplicates_detected": int(raw_result.get("duplicates_detected", 0) or 0),
        "rejected_rows": int(raw_result.get("rejected_rows", 0) or 0),
        "correction_rows_detected": int(raw_result.get("correction_rows_detected", 0) or 0),
        "warnings": list(raw_result.get("warnings", []) or []),
        "errors": list(raw_result.get("errors", []) or []),
        "summary": dict(raw_result.get("summary", {}) or {}),
        "added_rows": list(raw_result.get("added_rows", []) or []),
        "duplicate_rows": list(raw_result.get("duplicate_rows", []) or []),
        "rejected_row_details": list(raw_result.get("rejected_row_details", []) or []),
    }
    for key in SYNC_RESULT_KEYS:
        result.setdefault(key, [] if key.endswith("rows") or key in {"warnings", "errors", "rejected_row_details"} else None)
    return result


def _prepare_source_rows(rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None, source_key: str, source_file: str | None = None) -> pd.DataFrame:
    frame = _rows_frame(rows)
    if frame.empty:
        return frame
    prepared = frame.copy(deep=True)
    prepared["source_key"] = source_key
    if source_file is not None:
        prepared["source_file"] = str(source_file)
    return prepared


def sync_rows_by_source(
    rows: pd.DataFrame | Sequence[Mapping[str, Any]] | None,
    workspace_id: str,
    source_key: str,
    source_file: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    key = _normal_source_key(source_key)
    workspace = _workspace(workspace_id)
    prepared = _prepare_source_rows(rows, key, source_file=source_file)
    raw_result = append_performance_rows(
        prepared,
        workspace,
        source_key=key,
        source_file=source_file,
        dry_run=dry_run,
    )
    return _stable_result(key, workspace, dry_run, raw_result)


def sync_odds_lock_rows(rows, workspace_id: str, source_file: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    return sync_rows_by_source(rows, workspace_id, ODDS_LOCK_SOURCE, source_file=source_file, dry_run=dry_run)


def sync_pro_predictor_rows(rows, workspace_id: str, source_file: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    return sync_rows_by_source(rows, workspace_id, PRO_PREDICTOR_SOURCE, source_file=source_file, dry_run=dry_run)


def sync_report_studio_rows(rows, workspace_id: str, source_file: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    return sync_rows_by_source(rows, workspace_id, REPORT_STUDIO_SOURCE, source_file=source_file, dry_run=dry_run)


def sync_proof_center_rows(rows, workspace_id: str, source_file: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    return sync_rows_by_source(rows, workspace_id, PROOF_CENTER_SOURCE, source_file=source_file, dry_run=dry_run)


def sync_learning_rows(rows, workspace_id: str, source_file: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    return sync_rows_by_source(rows, workspace_id, LEARNING_PAGE_SOURCE, source_file=source_file, dry_run=dry_run)


def sync_uploaded_csv_rows(rows, workspace_id: str, source_file: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    return sync_rows_by_source(rows, workspace_id, UPLOADED_CSV_SOURCE, source_file=source_file, dry_run=dry_run)


def sync_generated_pick_rows(rows, workspace_id: str, source_file: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    return sync_rows_by_source(rows, workspace_id, GENERATED_PICK_SOURCE, source_file=source_file, dry_run=dry_run)


def sync_manual_review_rows(rows, workspace_id: str, source_file: str | None = None, dry_run: bool = False) -> dict[str, Any]:
    return sync_rows_by_source(rows, workspace_id, MANUAL_REVIEW_SOURCE, source_file=source_file, dry_run=dry_run)
