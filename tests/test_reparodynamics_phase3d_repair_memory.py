from __future__ import annotations

import json

import pandas as pd

import autonomous_betting_agent.ui_i18n_phase3d  # noqa: F401
from autonomous_betting_agent.reparodynamics_repair_memory import (
    classify_memory_status,
    extract_repair_memory_rows,
    manual_review_decision,
    repair_memory_to_frames,
    stable_repair_key,
    update_repair_memory,
)
from autonomous_betting_agent.reparodynamics_shadow_backtest import build_phase3c_report
from autonomous_betting_agent.ui_i18n import localize_dataframe


def _finding(candidate_type: str = "no_play", roi_delta: float = 0.05, profit_delta: float = 3.0, losses_delta: float = -2.0) -> dict:
    return {
        "title": "soccer_draw_risk",
        "finding_type": "shadow_tested_repair",
        "candidate_type": candidate_type,
        "affected_sport": "soccer",
        "affected_market_type": "moneyline",
        "sample_size": 80,
        "completed_rows_used": 80,
        "has_shadow_backtest": True,
        "decision": "future_manual_review",
        "eligible_for_manual_review": True,
        "comparison_metrics": {
            "ROI_delta": roi_delta,
            "profit_units_delta": profit_delta,
            "losses_delta": losses_delta,
            "avoided_losses": abs(losses_delta),
            "overfit_risk": "low",
            "confidence_level": "medium",
        },
    }


def _report(finding: dict | None = None) -> dict:
    finding = finding or _finding()
    return {
        "phase": "Phase 3C Shadow Backtest",
        "generated_at_utc": "2026-01-01T00:00:00Z",
        "shadow_tested_repairs": [finding],
        "data_blockers": [],
        "watchlists": [],
        "repair_candidates": [],
        "rejected_repairs": [],
        "manual_review_queue": [],
    }


def test_stable_repair_key_same_across_runs():
    first = stable_repair_key(_finding())
    second = stable_repair_key({**_finding(), "sample_size": 100, "decision_reason": "different run"})
    assert first == second


def test_update_repair_memory_increments_times_seen():
    memory = update_repair_memory(None, _report())
    memory = update_repair_memory(memory, _report())
    item = next(iter(memory["items"].values()))
    assert item["times_seen"] == 2


def test_phase3c_report_converts_to_memory_rows():
    rows = extract_repair_memory_rows(_report(), source="test")
    assert rows
    assert rows[0]["repair_key"]
    assert rows[0]["ROI_delta"] == 0.05


def test_missing_clv_data_blocker_memory_status():
    report = build_phase3c_report([{"result": "win", "decimal_price": 2.0}])
    memory = update_repair_memory(None, report)
    statuses = {item["memory_status"] for item in memory["items"].values()}
    assert "data_blocked" in statuses or "watchlist" in statuses


def test_low_sample_repair_not_phase4_candidate():
    memory = update_repair_memory(None, _report({**_finding(), "sample_size": 5, "completed_rows_used": 5}))
    item = next(iter(memory["items"].values()))
    assert item["memory_status"] in {"new", "watchlist", "keep_testing"}
    assert item["eligible_for_phase4_lockbox"] is False


def test_repeated_positive_roi_can_be_promising():
    memory = None
    for index in range(2):
        report = _report({**_finding(), "title": f"soccer_draw_risk_{index}"})
        memory = update_repair_memory(memory, report)
    statuses = {item["memory_status"] for item in memory["items"].values()}
    assert statuses <= {"promising", "new", "keep_testing"}


def test_manual_reject_and_approve_do_not_activate_repairs():
    memory = update_repair_memory(None, _report())
    key = next(iter(memory["items"].keys()))
    rejected = manual_review_decision(memory, key, "reject", reviewer="test", note="no")
    assert rejected["items"][key]["manual_status"] == "rejected"
    approved = manual_review_decision(rejected, key, "manual_approved_for_future", reviewer="test", note="yes")
    assert approved["items"][key]["manual_status"] == "manual_approved_for_future"
    assert approved["live_mutation"] == "FORBIDDEN"
    assert approved["repairs_applied_live"] == 0


def test_phase4_lockbox_candidate_requires_repetition_and_manual_approval():
    memory = None
    for _ in range(3):
        memory = update_repair_memory(memory, _report())
    key = next(iter(memory["items"].keys()))
    approved = manual_review_decision(memory, key, "manual_approved_for_future")
    assert approved["items"][key]["memory_status"] == "phase4_lockbox_candidate"
    assert approved["items"][key]["eligible_for_phase4_lockbox"] is True


def test_memory_does_not_mutate_input_and_is_json_serializable():
    report = _report()
    original = json.dumps(report, sort_keys=True)
    memory = update_repair_memory(None, report)
    assert json.dumps(report, sort_keys=True) == original
    json.dumps(memory, sort_keys=True)


def test_repair_memory_frames_and_spanish_localization():
    memory = update_repair_memory(None, _report())
    frames = repair_memory_to_frames(memory)
    assert "summary" in frames
    localized = localize_dataframe(pd.DataFrame([{"repair_key": "x", "memory_status": "keep_testing"}]), "es")
    assert "Clave de reparacion" in localized.columns
    assert localized.iloc[0]["Estado de memoria"] == "seguir probando"


def test_classify_memory_status_rejects_negative_repeat():
    status = classify_memory_status({"times_seen": 3, "total_completed_rows_used": 100, "avg_ROI_delta": -0.01, "total_profit_units_delta": -1, "avg_losses_delta": 1})
    assert status == "rejected"
