from __future__ import annotations

from copy import deepcopy

from autonomous_betting_agent.advisory_candidate_review import (
    MANUAL_CANDIDATE_BLOCKED,
    MANUAL_CANDIDATE_ONLY,
    REVIEW_BLOCKED,
    REVIEW_ELIGIBLE,
    REVIEW_PREDICTION_ONLY,
    REVIEW_WATCHLIST_ONLY,
    apply_manual_candidate_selection,
    candidate_review_blocker_summary,
    candidate_review_diagnostics,
    candidate_review_report_section,
    candidate_review_rows,
    candidate_review_summary,
)
from autonomous_betting_agent.advisory_odds_value_display import advisory_csv_frame, fresh_slate_readiness_check


def _row(**updates):
    row = {
        "event": "Team A vs Team B",
        "prediction": "Team A",
        "market_type": "h2h",
        "sportsbook": "Caliente",
        "bookmaker": "Caliente",
        "advisory_playable_status": "PLAYABLE_PLUS_EV",
        "advisory_calibrated_playable_status": "PLAYABLE_PLUS_EV",
        "advisory_explanation_status": "EXPLAINED_PLAYABLE_PLUS_EV",
        "advisory_sportsbook_source_type": "REAL_SPORTSBOOK",
        "advisory_is_real_sportsbook": True,
        "advisory_is_consensus_source": False,
        "advisory_market_completeness_status": "COMPLETE_MARKET",
        "advisory_no_vig_available": True,
        "advisory_stale_line_status": "FRESH",
        "advisory_shadow_readiness_status": "NEEDS_MORE_COMPLETED_EVENTS",
        "result_status": "pending",
    }
    row.update(updates)
    return row


def test_playable_explained_row_is_review_eligible():
    result = candidate_review_diagnostics(_row())
    assert result["advisory_manual_review_eligible"] is True
    assert result["advisory_manual_review_status"] == REVIEW_ELIGIBLE


def test_blocked_source_market_no_vig_and_stale_rows_are_not_eligible():
    samples = [
        _row(advisory_playable_status="BLOCKED_MISSING_ODDS", advisory_playable_reason="missing_decimal_odds"),
        _row(advisory_sportsbook_source_type="CONSENSUS_ONLY", advisory_is_consensus_source=True),
        _row(advisory_sportsbook_source_type="UNKNOWN_SOURCE", advisory_is_real_sportsbook=False),
        _row(advisory_market_completeness_status="INCOMPLETE_MARKET"),
        _row(advisory_no_vig_available=False),
        _row(advisory_stale_line_status="STALE"),
    ]
    for sample in samples:
        result = candidate_review_diagnostics(sample)
        assert result["advisory_manual_review_eligible"] is False
        assert result["advisory_manual_review_status"] == REVIEW_BLOCKED


def test_watchlist_and_prediction_only_statuses_are_context_only():
    watchlist = candidate_review_diagnostics(
        _row(
            advisory_playable_status="WATCHLIST_VALUE",
            advisory_calibrated_playable_status="WATCHLIST_VALUE",
            advisory_explanation_status="EXPLAINED_WATCHLIST_VALUE",
        )
    )
    prediction = candidate_review_diagnostics(
        _row(
            advisory_playable_status="PREDICTION_ONLY_NOT_PLUS_EV",
            advisory_calibrated_playable_status="PREDICTION_ONLY_NOT_PLUS_EV",
            advisory_explanation_status="EXPLAINED_PREDICTION_ONLY",
        )
    )
    assert watchlist["advisory_manual_review_status"] == REVIEW_WATCHLIST_ONLY
    assert prediction["advisory_manual_review_status"] == REVIEW_PREDICTION_ONLY


def test_shadow_readiness_is_context_only():
    result = candidate_review_diagnostics(_row(advisory_shadow_readiness_status="NEEDS_MORE_COMPLETED_EVENTS"))
    assert result["advisory_manual_review_status"] == REVIEW_ELIGIBLE
    assert "shadow_model_context_only" in result["advisory_manual_review_warnings"]


def test_manual_selection_marks_eligible_and_ineligible_rows():
    eligible = candidate_review_rows([_row()])[0]
    blocked = candidate_review_rows([_row(advisory_no_vig_available=False)])[0]
    selected_ids = [eligible["advisory_candidate_review_row_id"], blocked["advisory_candidate_review_row_id"]]
    selected = apply_manual_candidate_selection([eligible, blocked], selected_ids)
    by_id = {row["advisory_candidate_review_row_id"]: row for row in selected}
    assert by_id[selected_ids[0]]["advisory_candidate_review_status"] == MANUAL_CANDIDATE_ONLY
    assert by_id[selected_ids[1]]["advisory_candidate_review_status"] == MANUAL_CANDIDATE_BLOCKED


def test_review_helpers_do_not_mutate_input_rows():
    rows = [_row()]
    before = deepcopy(rows)
    candidate_review_rows(rows)
    apply_manual_candidate_selection(rows, [])
    assert rows == before


def test_review_summary_report_csv_and_readiness_accept_new_fields():
    rows = candidate_review_rows([
        _row(event_start_utc="2099-01-01T00:00:00Z", odds_timestamp="2099-01-01T00:00:00Z"),
        _row(advisory_no_vig_available=False, event_start_utc="2099-01-01T00:00:00Z", odds_timestamp="2099-01-01T00:00:00Z"),
    ])
    summary = candidate_review_summary(rows)
    blockers = candidate_review_blocker_summary(rows)
    report = candidate_review_report_section(rows)
    csv_frame = advisory_csv_frame(rows)
    readiness = fresh_slate_readiness_check(rows, now="2098-12-31T00:00:00Z")
    assert "advisory_manual_review_status" in summary.columns
    assert "candidate_blocker" in blockers.columns
    assert "Manual Advisory Candidate Review Gate" in report
    assert "advisory_candidate_review_status" in csv_frame.columns
    assert readiness["readiness_status"] in {
        "READY_FOR_ADVISORY_VALUE",
        "PARTIALLY_READY",
        "NEEDS_COMPLETE_MARKETS",
        "NEEDS_REAL_SPORTSBOOK_PRICES",
    }
