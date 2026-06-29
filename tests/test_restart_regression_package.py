import json

from autonomous_betting_agent import restart_regression_package as restart
from autonomous_betting_agent import dashboard_refresh_package as dash
from autonomous_betting_agent import local_review_checklist as review


def _proof_rows():
    return [
        {"proof_id": "p1", "event_id": "e1", "event": "A vs B", "selection": "A", "decimal_odds": "2.00", "model_probability": "60%", "result": "win", "sport": "tennis", "league": "atp"},
        {"proof_id": "p2", "event_id": "e1", "event": "A vs B", "selection": "B", "decimal_odds": "1.90", "model_probability": "45%", "result": "loss", "sport": "tennis", "league": "atp"},
    ]


def _decision_rows():
    return [
        {"row_id": "p1", "row_index": 0, "final_action": "PLAYABLE VALUE", "final_blockers": [], "baseline_EV": "0.10", "calibrated_EV": "0.20"},
        {"row_id": "p2", "row_index": 1, "final_action": "NO BET", "final_blockers": ["calibrated_ev_below_buffer"], "baseline_EV": "-0.05", "calibrated_EV": "-0.10"},
    ]


def test_parse_json_object_and_fingerprint_ignore_volatile_fields():
    parsed = restart.parse_json_object('{"schema_version":"x","generated_at_utc":"now"}')
    a = {"schema_version": "x", "generated_at_utc": "a", "dashboard_refresh_hash": "1", "row_count": 2}
    b = {"schema_version": "x", "generated_at_utc": "b", "dashboard_refresh_hash": "2", "row_count": 2}

    assert parsed["schema_version"] == "x"
    assert restart.package_fingerprint(a) == restart.package_fingerprint(b)


def test_compare_field_detects_mismatch():
    row = restart.compare_field("test", {"row_count": 2}, {"row_count": 3}, "row_count")

    assert row["status"] == "FAIL"
    assert row["expected"] == 2
    assert row["actual"] == 3


def test_dashboard_consistency_checks_pass_on_rebuild():
    dashboard = dash.build_dashboard_refresh_package("test_01", _proof_rows(), _proof_rows(), _decision_rows())
    rebuilt = dash.build_dashboard_refresh_package("test_01", _proof_rows(), _proof_rows(), _decision_rows())
    checks = restart.dashboard_consistency_checks(dashboard, rebuilt)

    assert checks
    assert all(row["status"] == "PASS" for row in checks)


def test_checklist_consistency_checks_pass_on_rebuild():
    dashboard = dash.build_dashboard_refresh_package("test_01", _proof_rows(), _proof_rows(), _decision_rows())
    checklist = review.build_local_review_checklist("test_01", _proof_rows(), _proof_rows(), _decision_rows(), dashboard)
    rebuilt = review.build_local_review_checklist("test_01", _proof_rows(), _proof_rows(), _decision_rows(), dashboard)
    checks = restart.checklist_consistency_checks(checklist, rebuilt)

    assert checks
    assert all(row["status"] == "PASS" for row in checks)


def test_json_round_trip_and_export_reload_pass():
    dashboard = dash.build_dashboard_refresh_package("test_01", _proof_rows(), _proof_rows(), _decision_rows())

    assert restart.json_round_trip_check("dashboard", dashboard)["status"] == "PASS"
    assert restart.export_reload_check("dashboard", dashboard)["status"] == "PASS"


def test_safety_checks_pass_for_preview_packages():
    dashboard = dash.build_dashboard_refresh_package("test_01", _proof_rows(), _proof_rows(), _decision_rows())
    checks = restart.safety_checks([dashboard])

    assert checks
    assert all(row["status"] == "PASS" for row in checks)


def test_build_restart_regression_package_from_text_exports():
    proof_csv = restart.csv_from_rows(_proof_rows())
    decision_csv = restart.csv_from_rows(_decision_rows())
    dashboard = dash.build_dashboard_refresh_package("test_01", _proof_rows(), _proof_rows(), _decision_rows())
    checklist = review.build_local_review_checklist("test_01", _proof_rows(), _proof_rows(), _decision_rows(), dashboard)
    report = restart.build_restart_regression_package_from_text(
        "test_01",
        proof_csv,
        proof_csv,
        decision_csv,
        dash.export_dashboard_refresh_json(dashboard),
        review.export_local_review_json(checklist),
    )
    payload = json.loads(restart.export_restart_regression_json(report))

    assert payload["schema_version"] == "restart_regression_package_v1"
    assert payload["proof_row_count"] == 2
    assert payload["decision_row_count"] == 2
    assert payload["restart_status"] == "RESTART SAFE"
    assert payload["preview_only"] is True
    assert payload["files_written"] == 0
    assert payload["live_changes"] == 0
    assert "check_id" in restart.export_restart_checks_csv(report)
    assert "restart_regression_hash" in restart.export_restart_manifest_json(report)


def test_restart_regression_has_no_external_client_paths():
    source = open("autonomous_betting_agent/restart_regression_package.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
