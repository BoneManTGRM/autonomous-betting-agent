from __future__ import annotations

from typing import Any, Mapping


def _report_dict(report: Any) -> dict[str, Any]:
    if hasattr(report, "to_dict"):
        data = report.to_dict()
        return dict(data) if isinstance(data, Mapping) else {}
    return dict(report or {}) if isinstance(report, Mapping) else {}


def _base_report(data: Mapping[str, Any]) -> Mapping[str, Any]:
    diagnostics = data.get("diagnostics", {}) or {}
    return diagnostics.get("base_report", {}) or {}


def _row_level(data: Mapping[str, Any]) -> Mapping[str, Any]:
    return _base_report(data).get("row_level", {}) or {}


def _quality(data: Mapping[str, Any]) -> Mapping[str, Any]:
    diagnostics = data.get("diagnostics", {}) or {}
    return diagnostics.get("data_quality", {}) or {}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value or default)
    except Exception:
        return default


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except Exception:
        return default


def _candidate_action(candidate: Mapping[str, Any]) -> str:
    pattern_type = str(candidate.get("pattern_type", "")).lower()
    pattern_name = str(candidate.get("pattern_name", "")).lower()
    evidence = str(candidate.get("evidence_summary", ""))
    if "duplicate" in pattern_type or "duplicate" in pattern_name:
        return "Count unique events separately from pick rows; block duplicate-event promotion until row/event mismatch is resolved."
    if "mixed" in pattern_type or "mixed" in pattern_name:
        return "Keep mixed-outcome events in review; require event-level grading before learning promotion."
    if "sample" in pattern_type or "sample" in pattern_name:
        return "Collect more graded rows before any calibration or RYE decision."
    if "data_limitation" in pattern_type or "unavailable" in evidence.lower():
        return "Treat missing fields as data-quality blockers; do not promote repair until required coverage exists."
    return "Evaluate this candidate counterfactually in Shadow Mode only; do not change live picks."


def shadow_result_rows(report: Any) -> list[dict[str, Any]]:
    data = _report_dict(report)
    candidates = list(data.get("pattern_candidates", []) or [])
    rows: list[dict[str, Any]] = []
    for idx, raw in enumerate(candidates, start=1):
        candidate = dict(raw or {})
        rows.append(
            {
                "rank": idx,
                "candidate_id": candidate.get("candidate_id", ""),
                "pattern_name": candidate.get("pattern_name", ""),
                "pattern_type": candidate.get("pattern_type", ""),
                "affected_scope": candidate.get("affected_scope", ""),
                "sample_size": _int(candidate.get("sample_size")),
                "evidence_summary": candidate.get("evidence_summary", ""),
                "current_live_behavior": "No live change. Existing picks, confidence, edge, EV, units, bankroll, and filters remain unchanged.",
                "shadow_mode_action": _candidate_action(candidate),
                "would_change_live_pick": "NO",
                "production_repair_allowed": "NO",
                "safety_decision": "Shadow Mode only; live mutation forbidden.",
            }
        )
    return rows


def shadow_summary(report: Any) -> dict[str, Any]:
    data = _report_dict(report)
    base = _base_report(data)
    row_level = _row_level(data)
    quality = _quality(data)
    candidates = shadow_result_rows(data)
    readiness = data.get("readiness", {}) or {}
    gate = data.get("activation_gate", {}) or {}
    checks = gate.get("checks", {}) or {}
    return {
        "run_id": data.get("run_id", ""),
        "schema_version": data.get("schema_version", ""),
        "rows_scanned": _int(base.get("total_rows")),
        "completed_rows": _int(row_level.get("completed")),
        "unique_events": _int((base.get("unique_event_level", {}) or {}).get("unique_events")),
        "duplicate_rows": _int((data.get("diagnostics", {}) or {}).get("duplicate_rows")),
        "mixed_outcome_events": _int((data.get("diagnostics", {}) or {}).get("mixed_outcome_events")),
        "data_quality_score": round(_float(quality.get("score")), 2),
        "candidate_count": len(candidates),
        "shadow_mode_active": bool(data.get("shadow_mode_active")) or str((data.get("reparodynamics_doctrine", {}) or {}).get("shadow_mode_activation", "")).upper() == "ON",
        "live_pick_changes": bool(data.get("live_pick_changes")),
        "production_repairs_active": bool(data.get("production_repairs_active")),
        "shadow_mode_ready": bool(readiness.get("Shadow_Mode_ready")),
        "repair_gate_status": gate.get("gate_status", "CLOSED"),
        "live_repair_allowed": bool(checks.get("live_repair_allowed")),
    }


def no_live_mutation_assertions(report: Any) -> dict[str, bool]:
    summary = shadow_summary(report)
    rows = shadow_result_rows(report)
    return {
        "production_repairs_off": summary["production_repairs_active"] is False,
        "live_pick_changes_off": summary["live_pick_changes"] is False,
        "live_repair_gate_closed": summary["repair_gate_status"] == "CLOSED" and summary["live_repair_allowed"] is False,
        "all_candidates_shadow_only": all(row["would_change_live_pick"] == "NO" and row["production_repair_allowed"] == "NO" for row in rows),
    }
