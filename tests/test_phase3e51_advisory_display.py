from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pandas as pd

import autonomous_betting_agent.advisory_i18n_phase3e5  # noqa: F401
from autonomous_betting_agent.advisory_odds_value_display import (
    ADVISORY_WARNING,
    advisory_csv_frame,
    advisory_report_text,
    advisory_summary_counts,
    blocked_reason_summary,
    duplicate_conflict_summary,
    line_shopping_summary,
    playable_table,
    prediction_only_table,
    proof_safety_comparison,
    sportsbook_hold_summary,
    stale_line_summary,
    validate_advisory_rows,
    watchlist_table,
)
from autonomous_betting_agent.odds_value_engine import build_advisory_odds_value_rows
from autonomous_betting_agent.ui_i18n import localize_dataframe

NOW = datetime(2026, 6, 28, 20, 0, 0, tzinfo=timezone.utc)


def source_row(selection: str, odds: float | None, probability: float, *, book: str = "BookA", event: str = "Team A at Team B", market: str = "h2h", quality: str = "STRONG SAMPLE", loaded: bool = True) -> dict[str, object]:
    row: dict[str, object] = {
        "event": event,
        "prediction": selection,
        "sport": "basketball",
        "league": "test league",
        "market_type": market,
        "bookmaker": book,
        "model_probability": probability,
        "expected_value_per_unit": 0.10,
        "model_market_edge": 0.12,
        "lock_ready": True,
        "publish_ready": True,
        "proof_hash": f"hash-{event}-{selection}-{book}",
        "proof_id": f"proof-{event}-{selection}-{book}",
        "locked_at_utc": "2026-06-28T18:00:00Z",
        "result_status": "pending",
        "odds_last_update": "2026-06-28T19:50:00Z",
        "event_start_utc": "2026-06-28T22:00:00Z",
        "model_quality_label": quality,
        "lr_model_loaded": loaded,
    }
    if odds is not None:
        row["decimal_price"] = odds
    return row


def fixture_rows() -> list[dict[str, object]]:
    return [
        source_row("Team A", 2.35, 0.58, book="BookA"),
        source_row("Team B", 1.70, 0.42, book="BookA"),
        source_row("Team A", 2.50, 0.58, book="BookB"),
        source_row("Team A", 1.35, 0.74, book="BookC", event="Favorite at Price"),
        source_row("Team B", 3.00, 0.26, book="BookC", event="Favorite at Price"),
        source_row("Watch A", 2.25, 0.55, book="BookD", event="Watch at Value", quality="DATA BLOCKED", loaded=False),
        source_row("Watch B", 1.85, 0.45, book="BookD", event="Watch at Value", quality="DATA BLOCKED", loaded=False),
        source_row("Missing Odds", None, 0.55, book="BookE", event="Missing Odds Game"),
        source_row("Stale A", 2.20, 0.55, book="BookF", event="Stale Game"),
        source_row("Stale B", 1.85, 0.45, book="BookF", event="Stale Game"),
    ]


def valued_rows() -> list[dict[str, object]]:
    rows = fixture_rows()
    rows[-2]["odds_last_update"] = "2026-06-28T19:00:00Z"
    rows[-1]["odds_last_update"] = "2026-06-28T19:00:00Z"
    return build_advisory_odds_value_rows(rows, now=NOW)


def test_advisory_summary_counts_and_filtered_tables() -> None:
    valued = valued_rows()
    counts = advisory_summary_counts(valued)
    assert counts["total_advisory_rows"] == len(valued)
    assert counts["PLAYABLE_PLUS_EV"] >= 1
    assert counts["WATCHLIST_VALUE"] >= 1
    assert counts["PREDICTION_ONLY_NOT_PLUS_EV"] >= 1
    assert counts["blocked_rows"] >= 1
    assert counts["stale_rows"] >= 1
    assert counts["duplicate_conflict_rows"] >= 1
    assert set(playable_table(valued)["advisory_playable_status"].unique()) == {"PLAYABLE_PLUS_EV"}
    assert set(watchlist_table(valued)["advisory_playable_status"].unique()) == {"WATCHLIST_VALUE"}
    assert set(prediction_only_table(valued)["advisory_playable_status"].unique()) == {"PREDICTION_ONLY_NOT_PLUS_EV"}


def test_grouped_diagnostic_tables() -> None:
    valued = valued_rows()
    blocked = blocked_reason_summary(valued)
    assert not blocked.empty
    assert "row_count" in blocked.columns
    hold = sportsbook_hold_summary(valued)
    assert {"event", "market_type", "sportsbook_or_bookmaker", "number_of_sides_detected"}.issubset(set(hold.columns))
    line = line_shopping_summary(valued)
    assert not line.empty
    assert float(line["advisory_line_shopping_gain"].fillna(0).max()) > 0
    stale = stale_line_summary(valued)
    assert not stale.empty
    assert set(stale["advisory_stale_line_status"]).issubset({"STALE", "UNKNOWN", "EVENT_STARTED", "HISTORICAL_ROW"})
    conflicts = duplicate_conflict_summary(valued)
    assert not conflicts.empty
    assert all((conflicts["advisory_duplicate_event_status"] != "UNIQUE_EVENT") | (conflicts["advisory_conflict_status"] != "NO_CONFLICT"))


def test_advisory_report_and_csv_are_advisory_only() -> None:
    valued = valued_rows()
    report = advisory_report_text(valued)
    assert "Safety confirmation" in report
    assert "No bets were placed" in report
    assert "Live application remains OFF" in report
    csv_frame = advisory_csv_frame(valued)
    assert not csv_frame.empty
    assert any(col.startswith("advisory_") for col in csv_frame.columns)
    assert "official_ev_pick" not in csv_frame.columns
    assert ADVISORY_WARNING.startswith("These are advisory value classifications")


def test_proof_safety_comparison_passes_and_fails_on_immutable_changes() -> None:
    original = fixture_rows()
    valued = build_advisory_odds_value_rows(deepcopy(original), now=NOW)
    safe = proof_safety_comparison(original, valued)
    assert safe["passed"] is True
    changed_probability = deepcopy(valued)
    changed_probability[0]["model_probability"] = 0.01
    assert proof_safety_comparison(original, changed_probability)["passed"] is False
    changed_ev = deepcopy(valued)
    changed_ev[0]["expected_value_per_unit"] = 99
    assert proof_safety_comparison(original, changed_ev)["passed"] is False
    changed_edge = deepcopy(valued)
    changed_edge[0]["model_market_edge"] = 99
    assert proof_safety_comparison(original, changed_edge)["passed"] is False
    changed_lock = deepcopy(valued)
    changed_lock[0]["lock_ready"] = False
    assert proof_safety_comparison(original, changed_lock)["passed"] is False
    changed_publish = deepcopy(valued)
    changed_publish[0]["publish_ready"] = False
    assert proof_safety_comparison(original, changed_publish)["passed"] is False
    changed_hash = deepcopy(valued)
    changed_hash[0]["proof_hash"] = "changed"
    assert proof_safety_comparison(original, changed_hash)["passed"] is False
    changed_id = deepcopy(valued)
    changed_id[0]["proof_id"] = "changed"
    assert proof_safety_comparison(original, changed_id)["passed"] is False
    changed_locked_at = deepcopy(valued)
    changed_locked_at[0]["locked_at_utc"] = "changed"
    assert proof_safety_comparison(original, changed_locked_at)["passed"] is False
    assert proof_safety_comparison(original, valued[:-1])["passed"] is False


def test_real_file_shaped_validation_does_not_mutate_source_or_reorder() -> None:
    original = fixture_rows()
    before = deepcopy(original)
    validation = validate_advisory_rows(original)
    assert original == before
    assert validation["total_rows"] == len(original)
    assert validation["advisory_rows_generated"] == len(original)
    assert validation["proof_safety_check_result"]["passed"] is True
    valued = build_advisory_odds_value_rows(original, now=NOW)
    for before_row, after_row in zip(original, valued):
        assert before_row["event"] == after_row["event"]
        assert before_row["prediction"] == after_row["prediction"]
        assert all((not key.startswith("advisory_")) for key in before_row)
        assert any(key.startswith("advisory_") for key in after_row)


def test_spanish_advisory_labels_resolve_without_breaking_english() -> None:
    frame = pd.DataFrame([{"advisory_playable_status": "PLAYABLE_PLUS_EV", "advisory_raw_EV": 0.12}])
    localized = localize_dataframe(frame, "es")
    assert any("asesor" in col.lower() for col in localized.columns)
    assert localized.iloc[0, 0] in {"JUGABLE +EV", "PLAYABLE_PLUS_EV"}
    english = localize_dataframe(frame, "en")
    assert "advisory_playable_status" in english.columns
