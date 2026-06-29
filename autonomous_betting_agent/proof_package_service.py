import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.dashboard_data_service import build_dashboard_data
from autonomous_betting_agent.dashboard_ui import dashboard_json_text, operator_top_positive_ev_picks
from autonomous_betting_agent.performance_ledger_service import (
    export_performance_csv,
    export_performance_json,
    rows_for_dashboard,
    summarize_performance,
    validate_ledger_integrity,
)
from autonomous_betting_agent.proof_center_control_service import get_dashboard_readiness, get_ledger_health, get_proof_center_status

PACKAGE_SCHEMA_VERSION = "3E.14.0"
PUBLIC_PACKAGE_TYPES = {"public", "client"}
PRIVATE_PACKAGE_TYPES = {"private", "internal_review"}
SUPPORTED_PACKAGE_TYPES = PUBLIC_PACKAGE_TYPES | PRIVATE_PACKAGE_TYPES
PROOF_READY_GRADE = "LEDGER-BACKED PROOF READY"
PROVISIONAL_GRADE = "PROVISIONAL / NOT FINAL PROOF"
EMPTY_GRADE = "EMPTY / NOT PROOF READY"
NO_PLAYABLE_POSITIVE_EV_MESSAGE = "No playable positive-EV picks available."
SOURCE_DISCLAIMER = (
    "Ledger-backed metrics are proof-grade only when the package is marked proof-ready. "
    "Fallback/session/upload metrics are provisional and not final proof."
)
BLOCKED_TERMS = (
    "source_file",
    "previous_row_hash",
    "correction_reason",
    "private_export_csv",
    "private_export_json",
    "api_key",
    "secret",
    "token",
    "bearer",
    "password",
)
BLOCKED_PATHS = ("/home/", "/mnt/", "c:\\", "data/private", ".env")
PACKAGE_HASH_EXCLUDE_KEYS = {
    "generated_at_utc",
    "package_id",
    "package_hash",
    "verification_manifest",
    "redaction_status",
    "warnings",
}
PUBLIC_EXPORT_EXCLUDE_KEYS = {
    "private_export_hash",
    "private_export_csv",
    "private_export_json",
    "audit_manifest",
    "ledger_health",
    "dashboard_readiness",
    "integrity_validation_result",
    "internal_warnings",
    "internal_errors",
    "duplicate_review_details",
    "row_hash_verification_summary",
    "schema_version",
    "last_row_hash",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _workspace(value: Any) -> str:
    text = str(value or "").strip().replace(" ", "_").lower()
    return text or "default"


def _json_safe(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return [_json_safe(item) for item in value.to_dict(orient="records")]
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _json_dumps(value: Any) -> str:
    return json.dumps(_json_safe(value), indent=2, sort_keys=True, ensure_ascii=True)


def _canonical_dumps(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash_text(prefix: str, value: str, length: int = 32) -> str:
    return f"{prefix}_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:length]}"


def _stable_package_payload(package: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in dict(package).items() if key not in PACKAGE_HASH_EXCLUDE_KEYS}


def build_package_hash(package: Mapping[str, Any]) -> str:
    return _hash_text("pkg_hash", _canonical_dumps(_stable_package_payload(package)), length=32)


def build_export_hash(*parts: str) -> str:
    return _hash_text("export_hash", "\n---ABA-PROOF-EXPORT---\n".join(parts), length=32)


def _package_id(workspace_id: str, package_type: str, package_hash: str) -> str:
    safe_workspace = _workspace(workspace_id)
    hash_fragment = str(package_hash).split("_")[-1][:12]
    return f"pkg_{safe_workspace}_{package_type}_{hash_fragment}"


def _frame_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    return _json_safe(frame.to_dict(orient="records"))


def _records_from_public_json(public_json: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(public_json or "{}")
        rows = payload.get("rows", []) if isinstance(payload, Mapping) else []
        return [dict(item) for item in rows if isinstance(item, Mapping)]
    except Exception:
        return []


def _last_sequence_from_rows(rows: Sequence[Mapping[str, Any]]) -> int:
    values: list[int] = []
    for row in rows or []:
        try:
            values.append(int(float(row.get("ledger_sequence") or 0)))
        except (TypeError, ValueError):
            continue
    return max(values) if values else 0


def _last_hash_from_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    best_sequence = -1
    best_hash = ""
    for row in rows or []:
        try:
            sequence = int(float(row.get("ledger_sequence") or 0))
        except (TypeError, ValueError):
            sequence = 0
        if sequence >= best_sequence:
            best_sequence = sequence
            best_hash = str(row.get("row_hash") or "")
    return best_hash


def _csv_from_records(records: Sequence[Mapping[str, Any]]) -> str:
    rows = [dict(row) for row in records or []]
    if not rows:
        return ""
    columns: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in columns:
                columns.append(key)
    handle = io.StringIO()
    writer = csv.DictWriter(handle, fieldnames=columns)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in columns})
    return handle.getvalue()


def _proof_grade(selected_source: str, ledger_rows: int, proof_ready: bool) -> str:
    if proof_ready:
        return PROOF_READY_GRADE
    if selected_source == "empty" or ledger_rows <= 0:
        return EMPTY_GRADE
    return PROVISIONAL_GRADE


def _readiness_warnings(selected_source: str, ledger_status: str, dashboard_ready: bool, ledger_rows: int, errors: Sequence[str], redaction_passed: bool) -> list[str]:
    warnings: list[str] = []
    if selected_source != "ledger":
        warnings.append("Package is not powered by durable ledger rows.")
    if ledger_status != "PASS":
        warnings.append("Ledger integrity is not PASS.")
    if not dashboard_ready:
        warnings.append("Dashboard is not proof-ready.")
    if ledger_rows <= 0:
        warnings.append("Ledger rows are empty.")
    if errors:
        warnings.append("Package has blocking errors.")
    if not redaction_passed:
        warnings.append("Public-safe redaction validation failed.")
    return warnings


def _redacted_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _redacted_value(item) for key, item in value.items() if str(key) not in PUBLIC_EXPORT_EXCLUDE_KEYS and str(key) not in BLOCKED_TERMS}
    if isinstance(value, list):
        return [_redacted_value(item) for item in value]
    return value


def public_export_view(package: Mapping[str, Any]) -> dict[str, Any]:
    return _redacted_value(dict(package))


def _scan_text(name: str, text: str) -> tuple[list[str], list[str]]:
    lowered = (text or "").lower()
    blocked_terms = [term for term in BLOCKED_TERMS if term.lower() in lowered]
    blocked_paths = [path for path in BLOCKED_PATHS if path.lower() in lowered]
    return [f"{name}:{term}" for term in blocked_terms], [f"{name}:{path}" for path in blocked_paths]


def _markdown_text(package: Mapping[str, Any], *, public_safe: bool) -> str:
    payload = public_export_view(package) if public_safe else dict(package)
    top_picks = payload.get("top_positive_ev_picks") or []
    top_summary = NO_PLAYABLE_POSITIVE_EV_MESSAGE if not top_picks else f"{len(top_picks)} playable positive-EV picks available."
    manifest = payload.get("verification_manifest") or {}
    lines = [
        f"# ABA Signal Pro Proof Package",
        "",
        f"Package ID: {payload.get('package_id', '')}",
        f"Workspace: {payload.get('workspace_id', '')}",
        f"Package type: {payload.get('package_type', '')}",
        f"Proof grade: {payload.get('proof_grade', '')}",
        f"Proof ready: {payload.get('proof_ready', False)}",
        f"Ledger backed: {payload.get('ledger_backed', False)}",
        "",
        "## Performance Summary",
        f"Record: {payload.get('wins', 0)}-{payload.get('losses', 0)} | Pushes: {payload.get('pushes', 0)} | Cancels: {payload.get('cancels', 0)}",
        f"Win rate excluding pushes/cancels: {payload.get('win_rate_ex_push_cancel', 0)}",
        f"ROI: {payload.get('ROI', 0)}",
        f"Profit units: {payload.get('profit_units', 0)}",
        f"Average CLV: {payload.get('average_CLV', '')}",
        f"Duplicate count: {payload.get('duplicate_count', 0)}",
        "",
        "## Top Positive-EV Summary",
        top_summary,
        "",
        "## Verification Manifest",
        f"Package hash: {manifest.get('package_hash', payload.get('package_hash', ''))}",
        f"Public export hash: {manifest.get('public_export_hash', payload.get('public_export_hash', ''))}",
        f"Ledger integrity: {manifest.get('ledger_integrity_status', payload.get('ledger_integrity_status', ''))}",
        f"Rows: {manifest.get('total_rows', payload.get('total_rows', 0))}",
        f"Unique events: {manifest.get('unique_events', payload.get('unique_events', 0))}",
        "",
        "## Disclaimer",
        str(payload.get("source_disclaimer") or SOURCE_DISCLAIMER),
    ]
    return "\n".join(lines)


def export_proof_package_json(package: Mapping[str, Any]) -> str:
    public_safe = str(package.get("package_type", "public")) in PUBLIC_PACKAGE_TYPES
    payload = public_export_view(package) if public_safe else dict(package)
    return _json_dumps(payload)


def export_proof_package_markdown(package: Mapping[str, Any]) -> str:
    public_safe = str(package.get("package_type", "public")) in PUBLIC_PACKAGE_TYPES
    return _markdown_text(package, public_safe=public_safe)


def export_proof_package_csv_bundle(package: Mapping[str, Any]) -> dict[str, str]:
    package_type = str(package.get("package_type", "public"))
    public_rows = package.get("public_safe_rows") or []
    bundle = {
        "public_safe_proof_rows.csv": package.get("public_export_csv") or _csv_from_records(public_rows),
        "verification_manifest.csv": _csv_from_records([package.get("verification_manifest") or {}]),
    }
    if package_type in PRIVATE_PACKAGE_TYPES:
        bundle["private_audit_proof_rows.csv"] = str(package.get("private_export_csv") or "")
    return bundle


def validate_public_package_redactions(package: Mapping[str, Any]) -> dict[str, Any]:
    checked_outputs: list[str] = []
    blocked_terms_found: list[str] = []
    blocked_paths_found: list[str] = []
    outputs = {
        "package": _json_dumps(package),
        "json": export_proof_package_json(package),
        "markdown": export_proof_package_markdown(package),
        "csv_bundle": "\n".join(export_proof_package_csv_bundle(package).values()),
    }
    for name, text in outputs.items():
        checked_outputs.append(name)
        terms, paths = _scan_text(name, text)
        blocked_terms_found.extend(terms)
        blocked_paths_found.extend(paths)
    errors: list[str] = []
    if blocked_terms_found or blocked_paths_found:
        errors.append("Public-safe redaction validation failed.")
    return {
        "passed": not errors,
        "blocked_terms_found": blocked_terms_found,
        "blocked_paths_found": blocked_paths_found,
        "checked_outputs": checked_outputs,
        "warnings": [],
        "errors": errors,
    }


def _package_readiness(package: Mapping[str, Any], redaction_status: Mapping[str, Any] | None = None) -> bool:
    redaction = redaction_status or package.get("redaction_status") or {}
    return bool(
        package.get("selected_source") == "ledger"
        and package.get("ledger_integrity_status") == "PASS"
        and package.get("dashboard_ready")
        and int(package.get("total_rows") or 0) > 0
        and not package.get("errors")
        and redaction.get("passed", False)
    )


def package_is_proof_ready(package: Mapping[str, Any]) -> bool:
    return _package_readiness(package)


def _verification_manifest(package: Mapping[str, Any]) -> dict[str, Any]:
    manifest = {
        "package_id": package.get("package_id", ""),
        "package_schema_version": package.get("package_schema_version", PACKAGE_SCHEMA_VERSION),
        "package_hash": package.get("package_hash", ""),
        "public_export_hash": package.get("public_export_hash", ""),
        "workspace_id": package.get("workspace_id", ""),
        "package_type": package.get("package_type", ""),
        "generated_at_utc": package.get("generated_at_utc", ""),
        "proof_grade": package.get("proof_grade", ""),
        "proof_ready": package.get("proof_ready", False),
        "ledger_backed": package.get("ledger_backed", False),
        "ledger_integrity_status": package.get("ledger_integrity_status", ""),
        "dashboard_ready": package.get("dashboard_ready", False),
        "selected_source": package.get("selected_source", ""),
        "total_rows": package.get("total_rows", 0),
        "unique_events": package.get("unique_events", 0),
        "row_hash_count": package.get("row_hash_count", 0),
        "redaction_status": (package.get("redaction_status") or {}).get("passed", False),
        "source_disclaimer": package.get("source_disclaimer", SOURCE_DISCLAIMER),
    }
    if "last_sequence" in package:
        manifest["last_sequence"] = package.get("last_sequence", 0)
    return manifest


def _finalize_package(package: dict[str, Any]) -> dict[str, Any]:
    package["public_export_hash"] = build_export_hash(str(package.get("public_export_csv") or ""), str(package.get("public_export_json") or ""))
    if package.get("package_type") in PRIVATE_PACKAGE_TYPES:
        package["private_export_hash"] = build_export_hash(str(package.get("private_export_csv") or ""), str(package.get("private_export_json") or ""))
    package["package_hash"] = build_package_hash(package)
    package["package_id"] = _package_id(str(package.get("workspace_id") or "default"), str(package.get("package_type") or "public"), package["package_hash"])
    package["redaction_status"] = validate_public_package_redactions(package) if package.get("package_type") in PUBLIC_PACKAGE_TYPES else {"passed": True, "blocked_terms_found": [], "blocked_paths_found": [], "checked_outputs": ["private package uses public-safe subset for sharing"], "warnings": [], "errors": []}
    package["proof_ready"] = _package_readiness(package, package.get("redaction_status"))
    package["proof_grade"] = _proof_grade(str(package.get("selected_source") or "empty"), int(package.get("total_rows") or 0), bool(package.get("proof_ready")))
    extra_warnings = _readiness_warnings(
        str(package.get("selected_source") or "empty"),
        str(package.get("ledger_integrity_status") or ""),
        bool(package.get("dashboard_ready")),
        int(package.get("total_rows") or 0),
        list(package.get("errors") or []),
        bool((package.get("redaction_status") or {}).get("passed")),
    )
    warnings = list(package.get("warnings") or [])
    for warning in extra_warnings:
        if warning not in warnings:
            warnings.append(warning)
    package["warnings"] = warnings
    package["package_hash"] = build_package_hash(package)
    package["package_id"] = _package_id(str(package.get("workspace_id") or "default"), str(package.get("package_type") or "public"), package["package_hash"])
    package["verification_manifest"] = _verification_manifest(package)
    return package


def _build_base_package(workspace_id: str | None = None, package_type: str = "public") -> dict[str, Any]:
    package_type = str(package_type or "public").strip().lower()
    if package_type not in SUPPORTED_PACKAGE_TYPES:
        raise ValueError(f"Unsupported package_type: {package_type}")
    workspace = _workspace(workspace_id)
    generated_at = _utc_now()
    dashboard_rows = rows_for_dashboard(workspace)
    dashboard = build_dashboard_data(dashboard_rows)
    performance = summarize_performance(workspace_id=workspace)
    integrity = validate_ledger_integrity(workspace_id=workspace)
    proof_status = get_proof_center_status(workspace)
    ledger_health = get_ledger_health(workspace)
    dashboard_readiness = get_dashboard_readiness(workspace)
    public_export_csv = export_performance_csv(workspace_id=workspace, public_safe=True)
    public_export_json = export_performance_json(workspace_id=workspace, public_safe=True)
    public_rows = _records_from_public_json(public_export_json)
    row_hash_count = sum(1 for row in public_rows if row.get("row_hash"))
    selected_source = str(dashboard_readiness.get("dashboard_selected_source") or ("ledger" if not dashboard_rows.empty else "empty"))
    ledger_rows = int(performance.get("total_rows", len(dashboard_rows)) or 0)
    top_picks = operator_top_positive_ev_picks(dashboard.get("top_positive_ev_picks") or [])
    warnings = list(performance.get("ledger_integrity", {}).get("warnings", []) or [])
    warnings.extend(list(proof_status.get("warnings", []) or []))
    warnings.extend(list(dashboard_readiness.get("warnings", []) or []))
    errors = list(integrity.get("errors", []) or [])
    errors.extend(list(proof_status.get("errors", []) or []))
    package = {
        "package_id": "",
        "package_schema_version": PACKAGE_SCHEMA_VERSION,
        "package_hash": "",
        "public_export_hash": "",
        "generated_at_utc": generated_at,
        "workspace_id": workspace,
        "package_type": package_type,
        "proof_grade": EMPTY_GRADE if ledger_rows <= 0 else PROVISIONAL_GRADE,
        "proof_ready": False,
        "ledger_backed": selected_source == "ledger",
        "ledger_integrity_status": integrity.get("status", performance.get("ledger_integrity_status", ledger_health.get("status", "PASS"))),
        "dashboard_ready": bool(dashboard_readiness.get("dashboard_ready", False)),
        "selected_source": selected_source,
        "total_rows": ledger_rows,
        "unique_events": performance.get("unique_events", dashboard.get("events_scanned", 0)),
        "wins": performance.get("wins", 0),
        "losses": performance.get("losses", 0),
        "pushes": performance.get("pushes", 0),
        "cancels": performance.get("cancels", 0),
        "win_rate_ex_push_cancel": performance.get("win_rate_ex_push_cancel", 0.0),
        "profit_units": performance.get("profit_units", 0.0),
        "ROI": performance.get("roi", 0.0),
        "average_CLV": performance.get("average_clv"),
        "duplicate_count": performance.get("duplicate_count", 0),
        "correction_count": performance.get("correction_count", 0),
        "public_safe_rows": public_rows,
        "top_positive_ev_picks": top_picks,
        "top_positive_ev_message": NO_PLAYABLE_POSITIVE_EV_MESSAGE if not top_picks else "",
        "proof_summary": dashboard.get("proof_summary", {}),
        "roi_summary": dashboard.get("roi_summary", {}),
        "clv_summary": dashboard.get("clv_summary", {}),
        "source_disclaimer": SOURCE_DISCLAIMER,
        "verification_manifest": {},
        "redaction_status": {"passed": False, "blocked_terms_found": [], "blocked_paths_found": [], "checked_outputs": [], "warnings": [], "errors": []},
        "warnings": warnings,
        "errors": errors,
        "public_export_csv": public_export_csv,
        "public_export_json": public_export_json,
        "row_hash_count": row_hash_count,
        "last_sequence": ledger_health.get("last_sequence", _last_sequence_from_rows(_frame_records(dashboard_rows))),
    }
    return _finalize_package(package)


def build_public_proof_package(workspace_id: str | None = None) -> dict[str, Any]:
    return _build_base_package(workspace_id=workspace_id, package_type="public")


def build_client_summary_package(workspace_id: str | None = None) -> dict[str, Any]:
    return _build_base_package(workspace_id=workspace_id, package_type="client")


def _private_fields(workspace: str) -> dict[str, Any]:
    private_csv = export_performance_csv(workspace_id=workspace, public_safe=False)
    private_json = export_performance_json(workspace_id=workspace, public_safe=False)
    ledger_rows = _frame_records(rows_for_dashboard(workspace))
    health = get_ledger_health(workspace)
    readiness = get_dashboard_readiness(workspace)
    integrity = validate_ledger_integrity(workspace_id=workspace)
    return {
        "private_export_csv": private_csv,
        "private_export_json": private_json,
        "audit_manifest": {
            "workspace_id": workspace,
            "rows_checked": integrity.get("rows_checked", 0),
            "ledger_integrity_status": integrity.get("status", "PASS"),
        },
        "ledger_health": health,
        "dashboard_readiness": readiness,
        "integrity_validation_result": integrity,
        "internal_warnings": list(health.get("warnings", []) or []) + list(readiness.get("warnings", []) or []),
        "internal_errors": list(health.get("errors", []) or []) + list(readiness.get("errors", []) or []),
        "correction review counts": {"correction_count": sum(1 for row in ledger_rows if str(row.get("record_type", "")).lower() == "correction")},
        "duplicate_review_details": {"duplicate_count": len({str(row.get("duplicate_key")) for row in ledger_rows if str(row.get("duplicate_key") or "")})},
        "row_hash_verification_summary": {
            "row_hash_count": sum(1 for row in ledger_rows if row.get("row_hash")),
            "last_row_hash": health.get("last_row_hash", _last_hash_from_rows(ledger_rows)),
        },
        "schema_version": integrity.get("schema_version", ""),
        "last_sequence": health.get("last_sequence", _last_sequence_from_rows(ledger_rows)),
        "last_row_hash": health.get("last_row_hash", _last_hash_from_rows(ledger_rows)),
    }


def build_private_audit_package(workspace_id: str | None = None) -> dict[str, Any]:
    package = _build_base_package(workspace_id=workspace_id, package_type="private")
    package.update(_private_fields(str(package.get("workspace_id") or "default")))
    return _finalize_package(package)


def build_internal_review_package(workspace_id: str | None = None) -> dict[str, Any]:
    package = _build_base_package(workspace_id=workspace_id, package_type="internal_review")
    package.update(_private_fields(str(package.get("workspace_id") or "default")))
    return _finalize_package(package)
