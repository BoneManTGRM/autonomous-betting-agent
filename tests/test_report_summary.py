import pandas as pd

from autonomous_betting_agent.report_summary import (
    REPORT_SUMMARY_FIELDS,
    append_report_summary_columns,
    build_report_summary_bundle,
    build_report_summary_table,
    render_report_summary_markdown,
)


def _sample_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "event": "Aces vs Liberty",
                "prediction": "Aces ML",
                "sport": "basketball",
                "official_publish_ready": True,
                "client_report_ready": True,
                "advisory_status": "playable",
                "bookmaker": "Caliente",
                "market_type": "h2h",
                "market_completeness_status": "complete",
                "manual_clv": "0.08",
                "validation_status": "passed",
                "odds_verified": True,
                "explanation_summary": "Positive edge with verified price and complete market.",
                "warning": "line movement",
                "manual_candidate_status": "reviewed",
                "fresh_slate_ready": True,
            },
            {
                "event": "Aces vs Liberty",
                "prediction": "Over 170.5",
                "sport": "basketball",
                "report_lane": "watchlist",
                "bookmaker": "Playdoit",
                "market_type": "totals",
                "missing_market_sides": "under side missing",
                "manual_clv_status": "pending",
                "validation_status": "warning",
                "explanation_summary": "Needs better price before playable review.",
                "advisory_warning": "market incomplete",
            },
            {
                "event": "Tigers vs Lions",
                "prediction": "Tigers spread",
                "sport": "soccer",
                "report_lane": "prediction only",
                "data_issue_reason": "missing odds",
                "bookmaker": "Codere",
                "market_type": "spreads",
                "validation_status": "blocked",
                "candidate_review_status": "needs manual review",
            },
        ]
    )


def test_report_summary_positive_path_counts_sections_and_appendix_fields():
    bundle = build_report_summary_bundle(_sample_rows())

    assert bundle.table["report_summary_status"] == "REPORT_READY_WITH_PLAYABLE_ROWS"
    assert bundle.table["report_summary_rows"] == 3
    assert bundle.table["report_summary_unique_events"] == 2
    assert bundle.table["report_summary_playable_count"] == 1
    assert bundle.table["report_summary_watchlist_count"] == 1
    assert bundle.table["report_summary_prediction_only_count"] == 1
    assert bundle.table["report_summary_blocked_count"] == 1
    assert "missing odds" in bundle.table["report_summary_top_blockers"]
    assert "line movement" in bundle.table["report_summary_top_warnings"]
    assert "Caliente" in bundle.table["report_summary_source_summary"]
    assert "h2h" in bundle.table["report_summary_market_summary"]
    assert "average=0.080" in bundle.table["report_summary_clv_summary"]
    assert "odds_verified=1/3" in bundle.table["report_summary_validation_summary"]

    for field in REPORT_SUMMARY_FIELDS:
        assert field in bundle.rows.columns
        assert field in bundle.csv_text


def test_report_summary_empty_missing_data_path_is_safe():
    bundle = build_report_summary_bundle(pd.DataFrame())

    assert bundle.table["report_summary_status"] == "NO_REPORT_ROWS"
    assert bundle.table["report_summary_rows"] == 0
    assert bundle.table["report_summary_unique_events"] == 0
    assert bundle.rows.shape[0] == 1
    for field in REPORT_SUMMARY_FIELDS:
        assert field in bundle.rows.columns


def test_report_text_includes_explanation_blocker_warning_clv_validation_sections():
    text = build_report_summary_bundle(_sample_rows()).markdown

    required = [
        "Executive Summary",
        "Fresh Slate Readiness Summary",
        "Advisory Status Counts",
        "Threshold Summary",
        "Explanation Summary",
        "Top Blockers",
        "Top Warnings",
        "Sportsbook Source Summary",
        "Market Completeness Summary",
        "Manual Candidate Review Summary",
        "Manual CLV Summary",
        "Validation Summary",
        "Row-Level Appendix / Export",
        "Safety Notes",
    ]
    for section in required:
        assert section in text
    assert "missing odds" in text
    assert "line movement" in text
    assert "CLV" in text
    assert "Validation" in text


def test_source_rows_are_not_mutated():
    source = _sample_rows()
    original_columns = list(source.columns)
    original = source.copy(deep=True)

    enriched = append_report_summary_columns(source)

    assert list(source.columns) == original_columns
    pd.testing.assert_frame_equal(source, original)
    assert any(field in enriched.columns for field in REPORT_SUMMARY_FIELDS)


def test_render_report_summary_markdown_accepts_prebuilt_table():
    table = build_report_summary_table(_sample_rows())
    text = render_report_summary_markdown(table)

    assert "Executive Summary" in text
    assert "Validation Summary" in text
    assert "Row-Level Appendix / Export" in text
