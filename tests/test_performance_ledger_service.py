import json

import pandas as pd
import pytest

from autonomous_betting_agent import performance_ledger_service as service
from autonomous_betting_agent import proof_performance_store as store
from autonomous_betting_agent.dashboard_data_service import build_dashboard_data


@pytest.fixture()
def isolated_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "LEDGER_CSV_PATH", tmp_path / "proof_performance_ledger.csv")
    monkeypatch.setattr(store, "LEDGER_JSON_PATH", tmp_path / "proof_performance_ledger.json")
    monkeypatch.setattr(store, "BACKUP_DIR", tmp_path / "ledger_backups")
    return tmp_path


def _row(event, pick, lane="playable", result="win", odds=2.0, clv=0.02, locked="2026-06-29T10:00:00Z"):
    return {
        "event": event,
        "pick": pick,
        "market_type": "h2h",
        "sportsbook": "Book A",
        "locked_at_utc": locked,
        "decimal_odds": odds,
        "model_probability": 0.6,
        "raw_implied_probability": 0.5,
        "no_vig_implied_probability": 0.52,
        "edge": 0.10,
        "no_vig_edge": 0.08,
        "expected_value": 0.20,
        "clv": clv,
        "stake_units": 1.0,
        "result": result,
        "report_lane": lane,
        "official_publish_ready": lane == "playable",
        "odds_verified": True,
    }


def _seed_rows():
    return [
        _row("Alpha vs Beta", "Alpha ML", lane="playable", result="win", odds=2.0, clv=0.03, locked="2026-06-29T10:00:00Z"),
        _row("Gamma vs Delta", "Gamma ML", lane="watchlist", result="loss", odds=1.8, clv=-0.01, locked="2026-06-29T11:00:00Z"),
        _row("Epsilon vs Zeta", "Epsilon ML", lane="avoid", result="push", odds=1.9, clv=0.0, locked="2026-06-29T12:00:00Z"),
    ]


def test_service_appends_reads_recent_rows_and_workspace_isolation(isolated_ledger):
    service.append_performance_rows(_seed_rows(), "client_a", source_key="generated")
    service.append_performance_rows([_row("Other vs Team", "Other ML", locked="2026-06-29T13:00:00Z")], "client_b", source_key="generated")

    all_rows = service.read_performance_ledger()
    client_a = service.read_workspace_rows("client_a")
    recent = service.read_recent_rows("client_a", limit=2)

    assert len(all_rows) == 4
    assert len(client_a) == 3
    assert len(recent) == 2
    assert recent.iloc[0]["event"] == "Epsilon vs Zeta"


def test_service_summary_roi_clv_lane_results_and_integrity(isolated_ledger):
    service.append_performance_rows(_seed_rows(), "client_a", source_key="generated")

    summary = service.summarize_performance("client_a")

    assert summary["total_rows"] == 3
    assert summary["total_active_rows"] == 3
    assert summary["unique_events"] == 3
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["pushes"] == 1
    assert summary["cancels"] == 0
    assert summary["win_rate_ex_push_cancel"] == 0.5
    assert summary["profit_units"] == 0.0
    assert summary["risked_units"] == 3.0
    assert summary["roi"] == 0.0
    assert summary["average_clv"] == 0.006667
    assert summary["playable_roi"]["wins"] == 1
    assert summary["watchlist_roi"]["losses"] == 1
    assert summary["avoid_tracking_result"]["pushes"] == 1
    assert summary["schema_version"] == store.SCHEMA_VERSION
    assert summary["ledger_integrity_status"] == "PASS"


def test_service_rows_for_dashboard_preserve_compatibility_columns(isolated_ledger):
    service.append_performance_rows(_seed_rows(), "client_a", source_key="generated")

    rows = service.rows_for_dashboard("client_a")
    dashboard = build_dashboard_data(rows)

    assert "bookmaker" in rows.columns
    assert "prediction" in rows.columns
    assert "public_event" in rows.columns
    assert "model_market_edge" in rows.columns
    assert "expected_value_per_unit" in rows.columns
    assert "manual_clv" in rows.columns
    assert dashboard["events_scanned"] == 3
    assert dashboard["positive_ev_picks"] == 1
    assert dashboard["watchlist_picks"] == 1
    assert dashboard["avoid_picks"] == 1


def test_service_correction_include_exclude_behavior(isolated_ledger):
    original = service.append_performance_rows([_row("Alpha vs Beta", "Alpha ML")], "client_a", source_key="generated")["added_rows"][0]
    correction = _row("Alpha vs Beta", "Alpha ML", result="loss")
    correction["record_type"] = "correction"
    correction["corrected_from_proof_id"] = original["proof_id"]
    correction["correction_reason"] = "result correction"
    service.append_performance_rows([correction], "client_a", source_key="correction_record")

    included = service.summarize_performance("client_a", include_corrections=True)
    excluded = service.summarize_performance("client_a", include_corrections=False)

    assert included["total_rows"] == 2
    assert included["correction_count"] == 1
    assert included["total_active_rows"] == 2
    assert included["wins"] == 1
    assert included["losses"] == 1
    assert excluded["total_active_rows"] == 1
    assert excluded["wins"] == 1
    assert excluded["losses"] == 0


def test_service_exports_private_public_json_csv_and_no_demo_data(isolated_ledger):
    service.append_performance_rows(_seed_rows(), "client_a", source_key="uploaded_csv", source_file="/private/client.csv")

    private_csv = service.export_performance_csv("client_a")
    public_csv = service.export_performance_csv("client_a", public_safe=True)
    private_json = service.export_performance_json("client_a")
    public_json = service.export_performance_json("client_a", public_safe=True)
    public_payload = json.loads(public_json)

    assert "source_file" in private_csv
    assert "source_file" not in public_csv
    assert "previous_row_hash" not in public_csv
    assert "source_file" in private_json
    assert "source_file" not in public_json
    assert public_payload["rows"][0]["proof_id"]
    assert public_payload["rows"][0]["row_hash"]
    assert "John Doe" not in public_json
    assert "NY Liberty -120" not in public_json


def test_service_empty_and_dry_run_safety_path(isolated_ledger):
    empty_summary = service.summarize_performance("client_a")
    dry_run = service.append_performance_rows(pd.DataFrame(_seed_rows()), "client_a", source_key="generated", dry_run=True)

    assert empty_summary["total_rows"] == 0
    assert empty_summary["ledger_integrity_status"] == "PASS"
    assert dry_run["rows_to_add"] == 3
    assert dry_run["dry_run"] is True
    assert not store.LEDGER_CSV_PATH.exists()
    assert not store.LEDGER_JSON_PATH.exists()


def test_service_function_exports_hash_helpers_are_available(isolated_ledger):
    record = service.normalize_performance_record(_row("Alpha vs Beta", "Alpha ML"), "client_a")

    assert service.build_duplicate_key(record) == record["duplicate_key"]
    assert service.build_row_hash(record) == record["row_hash"]
    assert service.build_proof_id(record) == record["proof_id"]
    assert service.validate_ledger_integrity()["status"] == "PASS"
