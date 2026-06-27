from __future__ import annotations

from autonomous_betting_agent.reparodynamics_shadow_results import no_live_mutation_assertions, shadow_result_rows, shadow_summary


def _report():
    return {
        "run_id": "run_1",
        "schema_version": "adaptive_repair_runner_phase_3b_shadow_v1",
        "production_repairs_active": False,
        "shadow_mode_active": True,
        "live_pick_changes": False,
        "reparodynamics_doctrine": {"shadow_mode_activation": "ON"},
        "diagnostics": {
            "base_report": {
                "total_rows": 81,
                "row_level": {"completed": 40},
                "unique_event_level": {"unique_events": 78},
            },
            "data_quality": {"score": 82.5},
            "duplicate_rows": 3,
            "mixed_outcome_events": 0,
        },
        "readiness": {"Shadow_Mode_ready": False},
        "activation_gate": {"gate_status": "CLOSED", "checks": {"live_repair_allowed": False}},
        "pattern_candidates": [
            {
                "candidate_id": "abc123",
                "pattern_name": "duplicate_event_risk_watchlist",
                "pattern_type": "duplicate_risk",
                "sample_size": 81,
                "affected_scope": "event_counting",
                "evidence_summary": "Duplicate rows=3; duplicate event names=0.",
            }
        ],
    }


def test_shadow_summary_reports_phase_3b_shadow_without_live_changes():
    summary = shadow_summary(_report())
    assert summary["rows_scanned"] == 81
    assert summary["candidate_count"] == 1
    assert summary["shadow_mode_active"] is True
    assert summary["live_pick_changes"] is False
    assert summary["production_repairs_active"] is False
    assert summary["repair_gate_status"] == "CLOSED"
    assert summary["live_repair_allowed"] is False


def test_shadow_result_rows_are_counterfactual_only():
    rows = shadow_result_rows(_report())
    assert rows[0]["would_change_live_pick"] == "NO"
    assert rows[0]["production_repair_allowed"] == "NO"
    assert "Shadow Mode only" in rows[0]["safety_decision"]
    assert "unique events" in rows[0]["shadow_mode_action"]


def test_no_live_mutation_assertions_all_pass():
    checks = no_live_mutation_assertions(_report())
    assert all(checks.values())
