import json

from autonomous_betting_agent import dashboard_refresh_package as dash


def _proof_rows():
    return [
        {"proof_id": "p1", "event_id": "e1", "event": "A vs B", "sport": "tennis", "league": "atp", "market_type": "moneyline", "sportsbook": "book_a", "selection": "A", "decimal_odds": "2.00", "model_probability": "60%", "result": "win", "stake_units": "1", "closing_decimal_odds": "1.90"},
        {"proof_id": "p2", "event_id": "e1", "event": "A vs B", "sport": "tennis", "league": "atp", "market_type": "moneyline", "sportsbook": "book_a", "selection": "B", "decimal_odds": "1.90", "model_probability": "45%", "result": "loss", "stake_units": "1", "closing_decimal_odds": "2.00"},
        {"proof_id": "p3", "event_id": "e2", "event": "C vs D", "sport": "wnba", "league": "wnba", "market_type": "spread", "sportsbook": "book_b", "selection": "C", "decimal_odds": "1.91", "model_probability": "52%", "result": "push", "stake_units": "1"},
        {"proof_id": "p4", "event_id": "e3", "event": "E vs F", "sport": "soccer", "league": "epl", "market_type": "1x2", "sportsbook": "book_c", "selection": "Draw", "decimal_odds": "3.20", "model_probability": "30%", "result": "pending", "stake_units": "1"},
    ]


def _decision_rows():
    return [
        {"row_id": "p1", "row_index": 0, "final_action": "PLAYABLE VALUE", "final_blockers": [], "baseline_EV": "0.10", "calibrated_EV": "0.20", "CLV_decimal_delta": "0.10", "price_quality": "playable_price", "simulated_stake_fraction": "0.03"},
        {"row_id": "p2", "row_index": 1, "final_action": "NO BET", "final_blockers": ["calibrated_ev_below_buffer"], "baseline_EV": "-0.05", "calibrated_EV": "-0.10", "CLV_decimal_delta": "-0.10", "price_quality": "bad_price", "simulated_stake_fraction": "0"},
        {"row_id": "p3", "row_index": 2, "final_action": "WATCH ONLY", "final_blockers": [], "baseline_EV": "0.00", "calibrated_EV": "0.01", "simulated_stake_fraction": "0"},
        {"row_id": "p4", "row_index": 3, "final_action": "WAIT FOR BETTER ODDS", "final_blockers": ["below_calibrated_minimum_playable_odds"], "baseline_EV": "-0.02", "calibrated_EV": "-0.01", "simulated_stake_fraction": "0"},
    ]


def test_result_status_classifies_rows():
    assert dash.result_status({"result": "Win"}) == "win"
    assert dash.result_status({"result": "lost"}) == "loss"
    assert dash.result_status({"result": "push"}) == "push"
    assert dash.result_status({"result": "cancelled"}) == "cancel"
    assert dash.result_status({"result": ""}) == "pending"


def test_row_profit_units_from_result_and_odds():
    assert dash.row_profit_units({"decimal_odds": "2.25"}, "win") == 1.25
    assert dash.row_profit_units({"decimal_odds": "2.25"}, "loss") == -1.0
    assert dash.row_profit_units({"decimal_odds": "2.25"}, "push") == 0.0


def test_summarize_records_counts_events_and_roi():
    enriched = dash.enriched_dashboard_rows(_proof_rows(), _decision_rows())
    summary = dash.summarize_records(enriched)

    assert summary["row_count"] == 4
    assert summary["unique_event_count"] == 3
    assert summary["duplicate_event_group_count"] == 1
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["pushes"] == 1
    assert summary["pending_count"] == 1
    assert summary["win_rate_ex_push_cancel"] == 0.5
    assert summary["total_profit_units"] == 0.0
    assert summary["roi"] == 0.0


def test_action_and_blocker_breakdowns():
    enriched = dash.enriched_dashboard_rows(_proof_rows(), _decision_rows())
    actions = dash.action_breakdown(enriched)
    blockers = dash.blocker_breakdown(enriched)

    assert {row["final_action"] for row in actions} >= {"PLAYABLE VALUE", "NO BET", "WATCH ONLY", "WAIT FOR BETTER ODDS"}
    assert any(row["blocker"] == "calibrated_ev_below_buffer" for row in blockers)


def test_event_and_segment_breakdowns_include_duplicates():
    enriched = dash.enriched_dashboard_rows(_proof_rows(), _decision_rows())
    events = dash.event_breakdown(enriched)
    segments = dash.segment_breakdown(enriched)

    assert any(row["is_duplicate_group"] for row in events)
    assert any(row["segment_group"] == "sport" and row["segment_value"] == "tennis" for row in segments)


def test_build_dashboard_refresh_package_with_decision_rows():
    report = dash.build_dashboard_refresh_package("test_01", _proof_rows(), _proof_rows(), _decision_rows())

    assert report["schema_version"] == "dashboard_refresh_package_v1"
    assert report["source_row_count"] == 4
    assert report["decision_row_count"] == 4
    assert report["unique_event_count"] == 3
    assert report["duplicate_event_group_count"] == 1
    assert report["status"] in {"DASHBOARD READY", "REVIEW REQUIRED"}
    assert report["preview_only"] is True
    assert report["files_written"] == 0
    assert report["live_changes"] == 0
    assert report["safety_gates"]["proof_overwrite"] == "FORBIDDEN"


def test_build_dashboard_refresh_package_from_text_exports():
    proof_csv = dash.csv_from_rows(_proof_rows())
    decision_csv = dash.csv_from_rows(_decision_rows())
    report = dash.build_dashboard_refresh_package_from_text("test_01", proof_csv, proof_csv, decision_csv)
    payload = json.loads(dash.export_dashboard_refresh_json(report))

    assert payload["schema_version"] == "dashboard_refresh_package_v1"
    assert "win_rate_ex_push_cancel" in dash.export_dashboard_summary_csv(report)
    assert "final_action" in dash.export_dashboard_rows_csv(report)
    assert "event_key" in dash.export_event_breakdown_csv(report)
    assert "is_duplicate_group" in dash.export_duplicate_groups_csv(report)
    assert "segment_group" in dash.export_segment_breakdown_csv(report)
    assert "blocker" in dash.export_blocker_breakdown_csv(report)
    assert "dashboard_refresh_hash" in dash.export_dashboard_manifest_json(report)


def test_dashboard_refresh_has_no_external_client_paths():
    source = open("autonomous_betting_agent/dashboard_refresh_package.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
