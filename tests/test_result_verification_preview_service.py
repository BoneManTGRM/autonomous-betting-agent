import json

from autonomous_betting_agent import result_verification_preview_service as svc


def _proof_row(event="A vs B", market_type="moneyline"):
    return {
        "proof_id": "p1",
        "sport": "tennis",
        "event": event,
        "event_start_utc": "2026-06-29T20:00:00Z",
        "pick": "A",
        "market_type": market_type,
        "sportsbook": "book",
        "decimal_odds": 2.0,
    }


def test_event_key_is_stable_across_row_and_payload():
    row = _proof_row()
    payload = {"sport": "tennis", "event": "A vs B", "event_start_utc": "2026-06-29T20:00:00Z"}

    assert svc.event_key(row) == svc.event_key(payload)


def test_normalize_score_payload_captures_source_score_and_confidence():
    score = svc.normalize_score_payload({
        "sport": "tennis",
        "event": "A vs B",
        "event_start_utc": "2026-06-29T20:00:00Z",
        "source": "sportsdataio",
        "home_score": 2,
        "away_score": 0,
        "result_confidence": 0.92,
    })

    assert score["source"] == "sportsdataio"
    assert score["final_score"] == "2-0"
    assert score["result_confidence"] == 0.92
    assert score["has_score"] is True


def test_normalize_clv_payload_calculates_clv_percent():
    clv = svc.normalize_clv_payload({
        "sport": "tennis",
        "event": "A vs B",
        "event_start_utc": "2026-06-29T20:00:00Z",
        "source": "the_odds_api",
        "locked_decimal_odds": 2.0,
        "closing_decimal_odds": 1.9,
    })

    assert clv["source"] == "the_odds_api"
    assert clv["CLV_decimal"] == -0.1
    assert clv["CLV_percent"] == -0.05
    assert clv["has_closing_line"] is True


def test_build_verification_preview_report_marks_grade_ready_when_score_present():
    row = _proof_row()
    score = {**row, "source": "sportsdataio", "home_score": 2, "away_score": 0, "result_confidence": 0.99}
    clv = {**row, "source": "the_odds_api", "locked_decimal_odds": 2.0, "closing_decimal_odds": 1.9}

    report = svc.build_verification_preview_report("test_01", [row], [score], [clv])

    assert report["overall_passed"] is True
    assert report["ready_count"] == 1
    assert report["manual_review_count"] == 0
    result = report["verification_rows"][0]
    assert result["verification_decision"] == "GRADE READY"
    assert result["final_score_source"] == "sportsdataio"
    assert result["final_score"] == "2-0"
    assert result["graded_at_utc"]
    assert result["clv_source"] == "the_odds_api"
    assert result["frozen_pick_logic"] is True


def test_missing_score_requires_manual_review():
    row = _proof_row()
    report = svc.build_verification_preview_report("test_01", [row], [], [])

    assert report["overall_passed"] is False
    assert report["manual_review_count"] == 1
    assert report["verification_rows"][0]["verification_decision"] == "NO SCORE"
    assert "missing final score" in report["verification_rows"][0]["manual_review_reasons"]


def test_low_confidence_and_unsupported_market_require_manual_review():
    row = _proof_row(market_type="player_prop")
    score = {**row, "home_score": 1, "away_score": 0, "result_confidence": 0.5}
    report = svc.build_verification_preview_report("test_01", [row], [score], [])

    assert report["overall_passed"] is False
    reasons = report["verification_rows"][0]["manual_review_reasons"]
    assert "low result confidence" in reasons
    assert "unsupported market type" in reasons


def test_unique_events_and_duplicate_rows_are_separated():
    row1 = _proof_row()
    row2 = {**_proof_row(), "proof_id": "p2", "market_type": "spread"}
    score = {**row1, "home_score": 2, "away_score": 0}

    report = svc.build_verification_preview_report("test_01", [row1, row2], [score], [])

    assert report["row_count"] == 2
    assert report["unique_events"] == 1
    assert report["duplicate_row_count"] == 1


def test_report_hash_stable_when_generated_at_changes():
    row = _proof_row()
    report = svc.build_verification_preview_report("test_01", [row], [], [])
    changed_time = dict(report, generated_at_utc="2099-01-01T00:00:00Z")
    changed_count = dict(report, manual_review_count=99)

    assert svc.build_verification_preview_hash(report) == svc.build_verification_preview_hash(changed_time)
    assert svc.build_verification_preview_hash(report) != svc.build_verification_preview_hash(changed_count)


def test_validate_report_blocks_overstated_pass_and_unfrozen_logic():
    report = svc.build_verification_preview_report("test_01", [_proof_row()], [], [])
    overstated = dict(report, overall_passed=True)
    overstated["report_hash"] = svc.build_verification_preview_hash(overstated)
    unfrozen = dict(report, frozen_pick_logic=False)
    unfrozen["report_hash"] = svc.build_verification_preview_hash(unfrozen)

    assert svc.validate_verification_preview_report(overstated)["passed"] is False
    assert svc.validate_verification_preview_report(unfrozen)["passed"] is False


def test_sanitized_export_omits_raw_reasons_and_errors():
    report = svc.build_verification_preview_report("test_01", [_proof_row()], [], [])
    payload = json.loads(svc.export_verification_preview_report_json(report, public_safe=True))

    assert "errors" not in payload
    assert "manual_review_reasons" not in json.dumps(payload)
    assert payload["manual_review_count"] == 1
    assert payload["verification_rows"][0]["final_score_source"] == ""


def test_service_has_no_network_write_or_result_mutation_paths():
    source = open("autonomous_betting_agent/result_verification_preview_service.py", encoding="utf-8").read()
    forbidden = (
        "requests.",
        "httpx.",
        "urllib.",
        "approve_ledger_import",
        "append_performance_rows",
        "sync_rows_by_source",
        "update_result",
        "delete_proof",
        "write_text",
        "write_bytes",
    )
    for token in forbidden:
        assert token not in source
