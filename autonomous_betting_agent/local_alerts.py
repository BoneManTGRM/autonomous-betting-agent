"""Small user-facing local alert helpers.

These helpers return structured messages and never raise. Pages can display them
with Streamlit without coupling business logic to UI calls.
"""

from __future__ import annotations

from typing import Any


def _alert(kind: str, title: str, message: str, severity: str = "warning", **extra: Any) -> dict[str, Any]:
    return {"kind": kind, "title": title, "message": message, "severity": severity, **extra}


def missing_api_key_alert(service: str = "odds API") -> dict[str, Any]:
    return _alert("missing_api_key", "Missing API key", f"{service} key is missing. Live scans may be unavailable until it is configured.")


def empty_scan_alert() -> dict[str, Any]:
    return _alert("empty_scan", "No rows found", "The scan returned no rows. Check filters, API status, and supported sports.")


def bad_price_alert(reason: str = "Price audit did not pass.") -> dict[str, Any]:
    return _alert("bad_price", "Price review required", f"{reason} Keep this row in review/research until verified.")


def duplicate_event_alert(count: int = 0) -> dict[str, Any]:
    return _alert("duplicate_event", "Duplicate or correlated event exposure", f"Detected {count} duplicate/correlated exposure warning(s). Review before official promotion.")


def missing_event_start_alert() -> dict[str, Any]:
    return _alert("missing_event_start", "Missing event start time", "Rows without event start time should not be promoted to official forward proof.")


def missing_proof_id_alert() -> dict[str, Any]:
    return _alert("missing_proof_id", "Missing proof ID", "Rows without proof IDs should not be counted as public proof.")


def sqlite_fallback_alert(error: str = "") -> dict[str, Any]:
    detail = f" Detail: {error}" if error else ""
    return _alert("sqlite_fallback", "Using CSV fallback", f"SQLite storage is unavailable, so local CSV fallback is being used.{detail}")


def grading_conflict_alert(proof_id: str = "") -> dict[str, Any]:
    suffix = f" for proof ID {proof_id}" if proof_id else ""
    return _alert("grading_conflict", "Grade conflict", f"A conflicting grade was detected{suffix}. Review before overwriting.")


def report_export_failure_alert(error: str = "") -> dict[str, Any]:
    detail = f" Detail: {error}" if error else ""
    return _alert("report_export_failure", "Report export failed", f"The report could not be exported locally.{detail}", severity="error")
