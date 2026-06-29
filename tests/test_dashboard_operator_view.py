import ast
from pathlib import Path

from autonomous_betting_agent.dashboard_data_service import DASHBOARD_FIELDS, build_dashboard_data
from autonomous_betting_agent.dashboard_ui import (
    API_HIGH_USAGE,
    API_OK,
    DASHBOARD_EMPTY,
    DASHBOARD_FALLBACK,
    DASHBOARD_LEDGER_BACKED,
    LEDGER_BACKED_PROOF_GRADE,
    NOT_PROOF_READY,
    OPERATOR_STATUS_CARD_KEYS,
    PRIMARY_KPI_KEYS,
    PROOF_PERFORMANCE_KEYS,
    PROOF_READY,
    PROVISIONAL_FALLBACK_NOT_FINAL_PROOF,
    RISK_HIGH,
    RISK_OK,
    operator_top_positive_ev_picks,
    operator_traffic_light_statuses,
)

PAGE = Path("pages/dashboard.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def _text_dict():
    return _assignment_value("TEXT")


def test_dashboard_imports_required_bridge_and_control_helpers():
    assert "from autonomous_betting_agent.dashboard_ledger_bridge import build_dashboard_from_ledger, dashboard_source_summary" in SOURCE
    assert "from autonomous_betting_agent.proof_center_control_service import get_dashboard_readiness, get_ledger_health, get_proof_center_status" in SOURCE
    assert "from autonomous_betting_agent.dashboard_data_service import build_dashboard_data" in SOURCE
    assert "build_dashboard_from_ledger(" in SOURCE
    assert "dashboard_source_summary(" in SOURCE
    assert "get_proof_center_status(" in SOURCE
    assert "get_ledger_health(" in SOURCE
    assert "get_dashboard_readiness(" in SOURCE


def test_operator_status_primary_kpi_and_proof_fields_exist():
    assert "dashboard_data_source" in OPERATOR_STATUS_CARD_KEYS
    assert "ledger_rows" in OPERATOR_STATUS_CARD_KEYS
    assert "selected_rows" in OPERATOR_STATUS_CARD_KEYS
    assert "dashboard_ready" in OPERATOR_STATUS_CARD_KEYS
    assert "ledger_integrity_status" in OPERATOR_STATUS_CARD_KEYS
    assert "model_status" in OPERATOR_STATUS_CARD_KEYS
    assert "drift_status" in OPERATOR_STATUS_CARD_KEYS
    assert "events_scanned" in PRIMARY_KPI_KEYS
    assert "positive_ev_picks" in PRIMARY_KPI_KEYS
    assert "watchlist_picks" in PRIMARY_KPI_KEYS
    assert "avoid_picks" in PRIMARY_KPI_KEYS
    assert "roi" in PRIMARY_KPI_KEYS
    assert "profit_units" in PRIMARY_KPI_KEYS
    assert "average_clv" in PRIMARY_KPI_KEYS
    assert "unique_events" in PROOF_PERFORMANCE_KEYS
    assert "wins" in PROOF_PERFORMANCE_KEYS
    assert "losses" in PROOF_PERFORMANCE_KEYS
    assert "duplicate_count" in PROOF_PERFORMANCE_KEYS
    assert "correction_count" in PROOF_PERFORMANCE_KEYS


def test_dashboard_sections_are_present():
    for key in (
        "operator_status",
        "traffic_lights",
        "primary_kpis",
        "proof_performance",
        "top_picks",
        "risk_bankroll",
        "system_health",
        "sync_summary",
        "dashboard_readiness",
        "ledger_health",
        "proof_center_status",
    ):
        assert key in SOURCE


def test_dashboard_source_and_proof_grade_warning_logic_exists():
    assert "selected_source" in SOURCE
    assert "proof_grade_label" in SOURCE
    assert "ledger_warning" in SOURCE
    assert "ledger_empty" in SOURCE
    assert "integrity_warning" in SOURCE
    assert "api_high" in SOURCE
    assert "risk_high" in SOURCE
    assert "provisional" in SOURCE
    assert "ledger_backed" in SOURCE
    assert "proof-grade" in SOURCE
    assert "not final proof" in SOURCE


def test_traffic_light_status_labels_exist_and_work():
    assert PROOF_READY == "PROOF READY"
    assert NOT_PROOF_READY == "NOT PROOF READY"
    assert DASHBOARD_LEDGER_BACKED == "DASHBOARD LEDGER-BACKED"
    assert DASHBOARD_FALLBACK == "DASHBOARD FALLBACK"
    assert DASHBOARD_EMPTY == "DASHBOARD EMPTY"
    assert RISK_OK == "RISK OK"
    assert RISK_HIGH == "RISK HIGH"
    assert API_OK == "API OK"
    assert API_HIGH_USAGE == "API HIGH USAGE"
    assert LEDGER_BACKED_PROOF_GRADE == "Ledger-backed proof-grade"
    assert PROVISIONAL_FALLBACK_NOT_FINAL_PROOF == "Provisional fallback — not final proof"

    ledger_status = operator_traffic_light_statuses(
        {"api_usage": {"usage_fraction": 0.1}, "bankroll_summary": {"daily_exposure_fraction": 0.01}},
        {"ledger_integrity_status": "PASS"},
        {"status": "PASS", "warnings": [], "errors": []},
        {"dashboard_ready": True},
        {"selected_source": "ledger"},
    )
    fallback_status = operator_traffic_light_statuses(
        {"api_usage": {"usage_fraction": 0.95}, "bankroll_summary": {"daily_exposure_fraction": 0.12}},
        {},
        {"status": "PASS", "warnings": [], "errors": []},
        {"dashboard_ready": False},
        {"selected_source": "uploaded"},
    )

    assert ledger_status["proof_status"] == PROOF_READY
    assert ledger_status["dashboard_source_status"] == DASHBOARD_LEDGER_BACKED
    assert ledger_status["risk_status"] == RISK_OK
    assert ledger_status["api_status"] == API_OK
    assert fallback_status["proof_status"] == NOT_PROOF_READY
    assert fallback_status["dashboard_source_status"] == DASHBOARD_FALLBACK
    assert fallback_status["risk_status"] == RISK_HIGH
    assert fallback_status["api_status"] == API_HIGH_USAGE


def test_top_ev_picks_exclude_watchlist_and_avoid_rows():
    rows = [
        {"event": "Alpha vs Beta", "pick": "Alpha ML", "market": "h2h", "expected_value": 0.15, "report_lane": "playable"},
        {"event": "Gamma vs Delta", "pick": "Gamma ML", "market": "h2h", "expected_value": 0.25, "report_lane": "watchlist"},
        {"event": "Epsilon vs Zeta", "pick": "Zeta ML", "market": "h2h", "expected_value": 0.30, "report_lane": "avoid"},
        {"event": "Eta vs Theta", "pick": "Eta ML", "market": "h2h", "expected_value": -0.10, "report_lane": "playable"},
    ]

    picks = operator_top_positive_ev_picks(rows)

    assert len(picks) == 1
    assert picks[0]["event"] == "Alpha vs Beta"
    assert picks[0]["expected_value"] == 0.15
    assert all("watch" not in str(row.get("report_lane", "")).lower() for row in picks)
    assert all("avoid" not in str(row.get("report_lane", "")).lower() for row in picks)


def test_empty_top_ev_state_and_dashboard_contract_remain_compatible():
    assert operator_top_positive_ev_picks([
        {"event": "Only Watch", "pick": "Watch", "expected_value": 0.20, "report_lane": "watchlist"},
        {"event": "Only Avoid", "pick": "Avoid", "expected_value": 0.20, "report_lane": "avoid"},
    ]) == []
    assert "top_picks_empty" in SOURCE
    dashboard = build_dashboard_data([])
    assert all(field in dashboard for field in DASHBOARD_FIELDS)


def test_dashboard_is_read_only_and_has_no_import_write_path():
    forbidden = (
        "append_performance_rows",
        "sync_rows_by_source",
        "approve_ledger_import",
        "preview_ledger_import",
        "create_correction",
        "apply_correction",
        "mutate_result",
        "update_result",
        "delete_proof",
    )
    for token in forbidden:
        assert token not in SOURCE
    assert "approve_import" not in SOURCE
    assert "Proof Center" not in SOURCE or "proof_center_status" in SOURCE


def test_no_fake_demo_values_and_empty_state_is_honest():
    forbidden_tokens = (
        "John Doe",
        "NY Liberty -120",
        "Aces vs Liberty",
        "Events Scanned\": 184",
        "Avoid Picks\": 158",
        "+8.4%",
    )
    for token in forbidden_tokens:
        assert token not in SOURCE
    assert "empty safety path" in SOURCE
    assert "No ledger, session, or uploaded rows found" in SOURCE


def test_english_and_spanish_operator_text_keys_exist():
    text = _text_dict()
    required = {
        "operator_status",
        "traffic_lights",
        "primary_kpis",
        "proof_performance",
        "top_picks",
        "top_picks_empty",
        "risk_bankroll",
        "system_health",
        "sync_summary",
        "dashboard_readiness",
        "ledger_health",
        "proof_center_status",
        "ledger_warning",
        "provisional",
        "ledger_backed",
        "raw_diagnostics",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_raw_json_diagnostic_view_is_collapsed_by_default():
    assert "with st.expander(t(\"raw_diagnostics\"), expanded=False):" in SOURCE
    assert "st.code(json_text, language=\"json\")" in SOURCE
    assert "dashboard_json_download" in SOURCE
