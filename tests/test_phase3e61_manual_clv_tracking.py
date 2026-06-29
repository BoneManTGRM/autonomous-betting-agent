from __future__ import annotations

from copy import deepcopy

from autonomous_betting_agent.advisory_clv_tracking import (
    CLV_INVALID_CLOSING_PRICE,
    CLV_INVALID_OPENING_PRICE,
    CLV_MISSING_CLOSING_PRICE,
    CLV_NEGATIVE,
    CLV_NEUTRAL,
    CLV_POSITIVE,
    apply_manual_clv_fields,
    clv_diagnostics,
    manual_clv_group_summary,
    manual_clv_report_section,
    manual_clv_status_counts,
    manual_clv_summary,
)
from autonomous_betting_agent.advisory_odds_value_display import advisory_csv_frame, fresh_slate_readiness_check


def _row(**updates):
    row = {
        "event": "Team A vs Team B",
        "prediction": "Team A",
        "market_type": "h2h",
        "sportsbook": "Caliente",
        "bookmaker": "Caliente",
        "decimal_odds": 2.10,
        "closing_decimal_odds": 1.90,
        "model_probability": 0.58,
        "advisory_playable_status": "PLAYABLE_PLUS_EV",
        "advisory_calibrated_playable_status": "PLAYABLE_PLUS_EV",
        "advisory_explanation_status": "EXPLAINED_PLAYABLE_PLUS_EV",
        "advisory_sportsbook_source_type": "REAL_SPORTSBOOK",
        "advisory_market_completeness_status": "COMPLETE_MARKET",
        "advisory_no_vig_available": True,
        "event_start_utc": "2099-01-01T00:00:00Z",
        "odds_timestamp": "2099-01-01T00:00:00Z",
    }
    row.update(updates)
    return row


def test_positive_negative_and_neutral_clv_statuses():
    positive = clv_diagnostics(_row(decimal_odds=2.10, closing_decimal_odds=1.90))
    negative = clv_diagnostics(_row(decimal_odds=1.80, closing_decimal_odds=2.00))
    neutral = clv_diagnostics(_row(decimal_odds=2.00, closing_decimal_odds=2.00))
    assert positive["advisory_clv_status"] == CLV_POSITIVE
    assert positive["advisory_clv_decimal_delta"] == 0.2
    assert negative["advisory_clv_status"] == CLV_NEGATIVE
    assert neutral["advisory_clv_status"] == CLV_NEUTRAL


def test_missing_and_invalid_prices_are_handled_safely():
    missing = clv_diagnostics(_row(closing_decimal_odds=None))
    invalid_close = clv_diagnostics(_row(closing_decimal_odds="bad"))
    invalid_open = clv_diagnostics(_row(decimal_odds="bad"))
    assert missing["advisory_clv_status"] == CLV_INVALID_CLOSING_PRICE
    assert invalid_close["advisory_clv_status"] == CLV_INVALID_CLOSING_PRICE
    assert invalid_open["advisory_clv_status"] == CLV_INVALID_OPENING_PRICE
    assert clv_diagnostics({"event": "No prices"})["advisory_clv_status"] == CLV_INVALID_OPENING_PRICE
    assert clv_diagnostics(_row(closing_decimal_odds=None, manual_closing_decimal_odds=None))["advisory_clv_status"] == CLV_INVALID_CLOSING_PRICE
    no_close_field = _row()
    no_close_field.pop("closing_decimal_odds")
    assert clv_diagnostics(no_close_field)["advisory_clv_status"] == CLV_MISSING_CLOSING_PRICE


def test_apply_manual_clv_fields_does_not_mutate_input_rows():
    rows = [_row()]
    before = deepcopy(rows)
    out = apply_manual_clv_fields(rows)
    assert rows == before
    assert out[0]["advisory_clv_status"] == CLV_POSITIVE


def test_clv_summaries_status_counts_and_report():
    rows = [
        _row(decimal_odds=2.10, closing_decimal_odds=1.90),
        _row(decimal_odds=1.80, closing_decimal_odds=2.00, bookmaker="Codere"),
        _row(decimal_odds=2.00, closing_decimal_odds=2.00, market_type="spread"),
    ]
    summary = manual_clv_summary(rows)
    by_book = manual_clv_group_summary(rows, "bookmaker")
    counts = manual_clv_status_counts(rows)
    report = manual_clv_report_section(rows)
    assert "advisory_clv_status" in summary.columns
    assert "bookmaker" in by_book.columns
    assert counts[CLV_POSITIVE] == 1
    assert counts[CLV_NEGATIVE] == 1
    assert counts[CLV_NEUTRAL] == 1
    assert "Manual CLV Tracking" in report


def test_clv_fields_export_and_do_not_break_readiness():
    rows = apply_manual_clv_fields([_row()])
    csv_frame = advisory_csv_frame(rows)
    readiness = fresh_slate_readiness_check(rows, now="2098-12-31T00:00:00Z")
    assert "advisory_clv_status" in csv_frame.columns
    assert "advisory_closing_decimal_odds" in csv_frame.columns
    assert readiness["readiness_status"] in {
        "READY_FOR_ADVISORY_VALUE",
        "PARTIALLY_READY",
        "NEEDS_COMPLETE_MARKETS",
        "NEEDS_REAL_SPORTSBOOK_PRICES",
    }
