from __future__ import annotations

from autonomous_betting_agent.correlation import (
    correlation_warnings,
    detect_duplicate_event_picks,
    detect_duplicate_proof_ids,
    detect_same_event_exposure,
    one_official_pick_per_event_filter,
)


def _row(proof_id: str, market: str = "moneyline", score: int = 50):
    return {
        "proof_id": proof_id,
        "sport": "NBA",
        "event_name": "A vs B",
        "event_start_time": "2026-06-23T12:00:00Z",
        "prediction": "A",
        "market": market,
        "ledger_type": "official",
        "pattern_points": score,
    }


def test_duplicate_proof_ids_detected():
    duplicates = detect_duplicate_proof_ids([_row("P1"), _row("P1")])
    assert duplicates == [{"proof_id": "P1", "count": 2}]


def test_duplicate_event_pick_detected():
    duplicates = detect_duplicate_event_picks([_row("P1"), _row("P2")])
    assert duplicates[0]["count"] == 2


def test_same_event_multiple_official_rows_flagged():
    exposure = detect_same_event_exposure([_row("P1"), _row("P2", market="spread")])
    assert exposure[0]["official_rows"] == 2


def test_one_official_pick_per_event_filter_keeps_highest_score():
    rows = [_row("P1", score=60), _row("P2", score=90)]
    kept = one_official_pick_per_event_filter(rows)
    assert len(kept) == 1
    assert kept[0]["proof_id"] == "P2"


def test_correlation_warnings_returns_strings():
    warnings = correlation_warnings([_row("P1"), _row("P1")])
    assert warnings
    assert any("Duplicate proof ID" in warning for warning in warnings)
