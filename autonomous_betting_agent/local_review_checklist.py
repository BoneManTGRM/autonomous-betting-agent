from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.dashboard_refresh_package import build_dashboard_refresh_package, parse_csv_text, csv_from_rows

SCHEMA_VERSION = "local_review_checklist_v1"
READY_TO_REVIEW = "READY TO REVIEW"
ACTION_REQUIRED = "ACTION REQUIRED"
BLOCKED = "BLOCKED"
SHADOW_ONLY = "SHADOW ONLY"
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
FORBIDDEN = "FORBIDDEN"


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


def parse_json_object(json_text: str | None) -> dict[str, Any]:
    text = _text(json_text)
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {"parse_error": "invalid_json"}
    return value if isinstance(value, dict) else {"parse_error": "json_root_not_object"}


def _bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"1", "true", "yes", "y", "pass", "ok"}


def checklist_row(check_id: str, title: str, status: str, details: str = "", required: bool = True, next_action: str = "") -> dict[str, Any]:
    return {"check_id": check_id, "title": title, "status": status, "required": required, "details": details, "next_action": next_action}


def required_field_checks(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    aliases = {
        "event": ("event", "event_name", "matchup", "event_id"),
        "selection": ("selection", "pick", "prediction", "outcome"),
        "decimal_odds": ("decimal_odds", "decimal_price", "best_price", "odds_at_pick", "odds_decimal"),
        "model_probability": ("model_probability", "confidence", "probability", "final_probability"),
        "result": ("result", "grade", "outcome", "official_result", "final_result", "status", "result_status"),
    }
    checks = []
    for field, names in aliases.items():
        missing = sum(1 for row in rows or [] if not any(_text(row.get(name)) for name in names))
        required = field != "result"
        status = PASS if missing == 0 else WARN if not required else FAIL
        checks.append(checklist_row(f"field_{field}", f"Field available: {field}", status, f"missing_rows={missing}", required, "fill missing source fields" if missing else ""))
    return checks


def dashboard_checks(dashboard: Mapping[str, Any]) -> list[dict[str, Any]]:
    if not dashboard:
        return [checklist_row("dashboard_package", "Dashboard package available", FAIL, "missing", True, "build dashboard package")]
    gates = dashboard.get("safety_gates") or {}
    duplicate_count = int(dashboard.get("duplicate_event_group_count") or 0)
    unknown_count = int(dashboard.get("unknown_count") or 0)
    blocker_count = len(dashboard.get("blocker_breakdown") or [])
    return [
        checklist_row("dashboard_schema", "Dashboard schema present", PASS if _text(dashboard.get("schema_version")) else FAIL, _text(dashboard.get("schema_version")), True, "rebuild dashboard package"),
        checklist_row("dashboard_rows", "Dashboard has rows", PASS if int(dashboard.get("source_row_count") or 0) > 0 else FAIL, f"source_row_count={dashboard.get('source_row_count', 0)}", True, "load proof rows"),
        checklist_row("dashboard_status", "Dashboard status checked", PASS if dashboard.get("status") == "DASHBOARD READY" else WARN, _text(dashboard.get("status")), False, "review dashboard warnings"),
        checklist_row("dashboard_hash", "Dashboard hash present", PASS if _text(dashboard.get("dashboard_refresh_hash")) else FAIL, _text(dashboard.get("dashboard_refresh_hash")), True, "rebuild dashboard package"),
        checklist_row("safe_preview_mode", "Preview mode only", PASS if dashboard.get("preview_only", True) is True and int(dashboard.get("live_changes") or 0) == 0 else FAIL, f"preview_only={dashboard.get('preview_only', True)} live_changes={dashboard.get('live_changes', 0)}", True, "restore preview-only mode"),
        checklist_row("safe_gates", "Safety gates present", PASS if gates else FAIL, str(bool(gates)), True, "restore safety gates"),
        checklist_row("duplicate_review", "Duplicate event groups reviewed", WARN if duplicate_count else PASS, f"duplicate_event_group_count={duplicate_count}", False, "review unique events vs row count" if duplicate_count else ""),
        checklist_row("unknown_results", "Unknown results reviewed", WARN if unknown_count else PASS, f"unknown_count={unknown_count}", False, "normalize unknown result rows" if unknown_count else ""),
        checklist_row("blocker_review", "Decision blockers reviewed", WARN if blocker_count else PASS, f"blocker_reason_count={blocker_count}", False, "review no-bet and wait reasons" if blocker_count else ""),
    ]


def decision_checks(decision: Mapping[str, Any], decision_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in decision_rows or decision.get("decision_preview_rows") or []]
    playable = len([row for row in rows if _text(row.get("final_action")).upper() == "PLAYABLE VALUE"])
    return [
        checklist_row("decision_rows", "Decision rows available", PASS if rows else WARN, f"decision_rows={len(rows)}", False, "run decision preview" if not rows else ""),
        checklist_row("decision_safe", "Decision output is preview only", PASS if decision.get("preview_only", True) is True and int(decision.get("live_changes") or 0) == 0 else FAIL, f"preview_only={decision.get('preview_only', True)}", True, "restore decision preview safety"),
        checklist_row("playable_review", "Playable rows reviewed", PASS if playable else WARN, f"playable={playable}", False, "confirm no playable rows exist" if not playable else "review playable rows"),
    ]


def ack_checks(acks: Mapping[str, Any]) -> list[dict[str, Any]]:
    items = (
        ("inputs_reviewed", "Source inputs reviewed", "review source rows"),
        ("duplicates_reviewed", "Duplicates reviewed", "review duplicate event groups"),
        ("blockers_reviewed", "Blockers reviewed", "review blocker reasons"),
        ("exports_downloaded", "Exports downloaded", "download JSON/CSV exports"),
    )
    return [checklist_row(f"ack_{key}", title, PASS if _bool(acks.get(key)) else WARN, f"{key}={acks.get(key, False)}", False, action) for key, title, action in items]


def summarize_checklist(checks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pass_count = len([row for row in checks or [] if row.get("status") == PASS])
    warn_count = len([row for row in checks or [] if row.get("status") == WARN])
    fail_count = len([row for row in checks or [] if row.get("status") == FAIL])
    required_fail_count = len([row for row in checks or [] if row.get("required") and row.get("status") == FAIL])
    readiness = BLOCKED if required_fail_count else ACTION_REQUIRED if warn_count else READY_TO_REVIEW
    return {"readiness_status": readiness, "pass_count": pass_count, "warn_count": warn_count, "fail_count": fail_count, "required_failure_count": required_fail_count}


def next_actions_from_checks(checks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [{"check_id": row.get("check_id"), "status": row.get("status"), "next_action": row.get("next_action")} for row in checks or [] if row.get("status") in {WARN, FAIL} and _text(row.get("next_action"))]


def build_local_review_checklist(
    workspace_id: str | None = None,
    proof_rows: Sequence[Mapping[str, Any]] | None = None,
    history_rows: Sequence[Mapping[str, Any]] | None = None,
    decision_preview_rows: Sequence[Mapping[str, Any]] | None = None,
    dashboard_report: Mapping[str, Any] | None = None,
    decision_report: Mapping[str, Any] | None = None,
    review_acks: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    proof = [dict(row) for row in proof_rows or []]
    history = [dict(row) for row in history_rows or []]
    decision_rows = [dict(row) for row in decision_preview_rows or []]
    dashboard = dict(dashboard_report or {})
    if not dashboard and proof:
        dashboard = build_dashboard_refresh_package(workspace_id, proof, history, decision_rows)
    decision = dict(decision_report or {})
    checks = required_field_checks(proof) + dashboard_checks(dashboard) + decision_checks(decision, decision_rows) + ack_checks(review_acks or {})
    summary = summarize_checklist(checks)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "local_review_id": "",
        "mode": SHADOW_ONLY,
        "proof_row_count": len(proof),
        "history_row_count": len(history),
        "decision_row_count": len(decision_rows or decision.get("decision_preview_rows") or []),
        "dashboard_status": dashboard.get("status", ""),
        **summary,
        "checklist_rows": checks,
        "next_actions": next_actions_from_checks(checks),
        "dashboard_manifest": dashboard.get("manifest") or {},
        "safety_gates": {"live_mutation": FORBIDDEN, "model_training": FORBIDDEN, "stored_data_mutation": FORBIDDEN, "automatic_live_promotion": FORBIDDEN, "source_update": FORBIDDEN},
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": [row["next_action"] for row in next_actions_from_checks(checks)],
        "errors": [row["details"] for row in checks if row.get("required") and row.get("status") == FAIL],
    }
    report["local_review_id"] = stable_hash("local_review", {"workspace_id": workspace_id, "checks": checks}, 24)
    report["local_review_hash"] = stable_hash("local_review_hash", {k: v for k, v in report.items() if k != "generated_at_utc"}, 32)
    return report


def build_local_review_checklist_from_text(
    workspace_id: str | None = None,
    proof_csv_text: str | None = None,
    history_csv_text: str | None = None,
    decision_preview_csv_text: str | None = None,
    dashboard_json_text: str | None = None,
    decision_json_text: str | None = None,
    review_ack_json_text: str | None = None,
) -> dict[str, Any]:
    return build_local_review_checklist(workspace_id, parse_csv_text(proof_csv_text), parse_csv_text(history_csv_text), parse_csv_text(decision_preview_csv_text), parse_json_object(dashboard_json_text), parse_json_object(decision_json_text), parse_json_object(review_ack_json_text))


def export_local_review_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_local_review_checklist_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("checklist_rows") or [])


def export_local_review_next_actions_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("next_actions") or [])


def export_local_review_manifest_json(report: Mapping[str, Any]) -> str:
    manifest = {key: report.get(key) for key in ("schema_version", "workspace_id", "local_review_id", "local_review_hash", "generated_at_utc", "readiness_status", "pass_count", "warn_count", "fail_count", "preview_only", "files_written", "live_changes")}
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
