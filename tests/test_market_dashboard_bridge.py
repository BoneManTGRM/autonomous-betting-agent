import json

from autonomous_betting_agent import market_dashboard_bridge as bridge


def _market_rows():
    return [
        {
            "market_id": "m1",
            "event_id": "e1",
            "event": "A vs B",
            "sport": "tennis",
            "league": "atp",
            "sportsbook": "Book A",
            "market_type": "moneyline",
            "selection": "A",
            "decimal_odds": 2.1,
            "calibrated_probability": 0.58,
            "calibrated_edge": 0.104,
            "ev": 0.218,
            "risk_level": "LOW",
            "final_action": "PLAYABLE VALUE",
            "proof_id": "p1",
        },
        {
            "market_id": "m2",
            "event_id": "e2",
            "event": "C vs D",
            "sport": "wnba",
            "league": "wnba",
            "sportsbook": "Book B",
            "market_type": "spread",
            "selection": "C -2.5",
            "decimal_odds": 1.9,
            "calibrated_probability": 0.52,
            "calibrated_edge": -0.006,
            "ev": -0.012,
            "risk_level": "HIGH",
            "final_action": "NO BET",
            "proof_id": "p2",
        },
    ]


def _chain_rows():
    return [
        {
            "chain_id": "c1",
            "events": ["e1", "e3"],
            "markets": ["moneyline", "moneyline"],
            "selections": ["A", "E"],
            "sportsbooks": ["Book A", "Book C"],
            "combined_decimal_odds": 3.8,
            "combined_probability": 0.34,
            "combined_ev": 0.292,
            "risk_class": "MEDIUM",
            "final_action": "CHAIN PREVIEW",
        }
    ]


def _avoid_rows():
    return [
        {
            "sport": "wnba",
            "league": "wnba",
            "market_type": "spread",
            "sportsbook": "Book B",
            "row_count": 1,
            "blocked_ratio": 1.0,
            "avoid_reasons": ["negative or zero EV"],
        }
    ]


def test_build_tracking_row_contains_schema_fields():
    row = bridge.build_tracking_row(_market_rows()[0], "test_01")

    assert set(bridge.TRACKING_FIELDS).issubset(row.keys())
    assert row["workspace_id"] == "test_01"
    assert row["single_vs_chain"] == "single"
    assert row["odds_band"] == "2_00_to_2_99"
    assert row["confidence_band"] == "58_to_64"
    assert row["favorite_or_underdog"] == "underdog"
    assert row["tracking_id"].startswith("track_")


def test_build_tracking_rows_includes_chain_rows():
    rows = bridge.build_tracking_rows("test_01", _market_rows(), _chain_rows())

    assert len(rows) == 3
    assert any(row["single_vs_chain"] == "chain" for row in rows)
    assert any(row["chain_id"] == "c1" for row in rows)


def test_validate_tracking_schema_passes_generated_rows():
    rows = bridge.build_tracking_rows("test_01", _market_rows(), _chain_rows())
    checks = bridge.validate_tracking_schema(rows)

    assert all(row["status"] in {"PASS", "WARN"} for row in checks)
    assert not any(row["status"] == "FAIL" for row in checks)


def test_dashboard_cards_count_actions_and_best_play():
    cards = bridge.summarize_market_cards(_market_rows(), _chain_rows(), _avoid_rows())

    assert cards["market_rows"] == 2
    assert cards["playable_count"] == 1
    assert cards["no_play_count"] == 1
    assert cards["chain_preview_count"] == 1
    assert cards["avoid_count"] == 1
    assert cards["best_play"]["event_id"] == "e1"


def test_segment_summary_groups_by_sport_league_market_book():
    rows = bridge.build_tracking_rows("test_01", _market_rows(), [])
    summary = bridge.segment_summary(rows)

    assert len(summary) == 2
    assert any(row["sport"] == "tennis" and row["playable_count"] == 1 for row in summary)
    assert any(row["market_type"] == "spread" and row["no_play_count"] == 1 for row in summary)


def test_proof_handoff_rows_are_operator_review_only():
    rows = bridge.build_tracking_rows("test_01", _market_rows(), [])
    handoff = bridge.proof_handoff_rows(rows)

    assert len(handoff) == 2
    assert all(row["handoff_status"] == "READY FOR OPERATOR REVIEW" for row in handoff)
    assert handoff[0]["tracking_id"] == rows[0]["tracking_id"]


def test_build_market_dashboard_bridge_from_report_exports():
    optimizer_report = {
        "workspace_id": "test_01",
        "preview_only": True,
        "live_changes": 0,
        "market_hunter_rows": _market_rows(),
        "chain_builder_rows": _chain_rows(),
        "avoid_list": _avoid_rows(),
    }
    report = bridge.build_market_dashboard_bridge("test_01", optimizer_report)
    payload = json.loads(bridge.export_market_bridge_json(report))

    assert payload["schema_version"] == "market_dashboard_bridge_v1"
    assert payload["tracking_schema_version"] == "market_tracking_schema_v1"
    assert payload["bridge_status"] == "DASHBOARD READY"
    assert payload["tracking_row_count"] == 3
    assert payload["preview_only"] is True
    assert payload["files_written"] == 0
    assert payload["live_changes"] == 0
    assert "tracking_id" in bridge.export_tracking_schema_csv(report)
    assert "market_type" in bridge.export_segment_summary_csv(report)
    assert "handoff_status" in bridge.export_proof_handoff_csv(report)
    assert "playable_count" in bridge.export_dashboard_cards_json(report)
    assert "check_id" in bridge.export_market_bridge_checks_csv(report)
    assert "bridge_hash" in bridge.export_market_bridge_manifest_json(report)


def test_build_market_dashboard_bridge_from_text_uses_optimizer_json():
    optimizer_report = {
        "workspace_id": "test_01",
        "preview_only": True,
        "live_changes": 0,
        "market_hunter_rows": _market_rows(),
        "chain_builder_rows": _chain_rows(),
        "avoid_list": _avoid_rows(),
    }
    report = bridge.build_market_dashboard_bridge_from_text("test_01", json.dumps(optimizer_report), "", "", "")

    assert report["market_row_count"] == 2
    assert report["chain_row_count"] == 1
    assert report["avoid_row_count"] == 1


def test_build_market_dashboard_bridge_blocks_empty_input():
    report = bridge.build_market_dashboard_bridge("test_01", {})

    assert report["bridge_status"] == "BLOCKED"
    assert any(row["check_id"] == "optimizer_rows_present" and row["status"] == "FAIL" for row in report["bridge_checks"])


def test_market_dashboard_bridge_has_no_external_client_paths():
    source = open("autonomous_betting_agent/market_dashboard_bridge.py", encoding="utf-8").read()
    for token in ("requests" + ".", "httpx" + ".", "urllib" + "."):
        assert token not in source
