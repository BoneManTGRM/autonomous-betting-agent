from autonomous_betting_agent.event_list_dedupe import collapse_to_event_rows, event_duplicate_summary, event_group_key, row_market_key


def test_event_group_key_groups_same_event_variants_but_keeps_market_keys_distinct():
    moneyline = {
        "event": "Mexico at Czech Republic",
        "event_start_utc": "2026-06-27T20:00:00Z",
        "prediction": "Mexico",
        "market_type": "moneyline",
    }
    total = {
        **moneyline,
        "prediction": "Over 2.5",
        "market_type": "totals",
        "line_point": 2.5,
    }

    assert event_group_key(moneyline) == event_group_key(total)
    assert row_market_key(moneyline) != row_market_key(total)


def test_collapse_to_event_rows_keeps_one_display_row_per_event():
    rows = [
        {
            "event": "Mexico at Czech Republic",
            "event_start_utc": "2026-06-27T20:00:00Z",
            "prediction": "Mexico",
            "market_type": "moneyline",
        },
        {
            "event": "Mexico at Czech Republic",
            "event_start_utc": "2026-06-27T20:00:00Z",
            "prediction": "Over 2.5",
            "market_type": "totals",
        },
        {
            "event": "Germany at Ecuador",
            "event_start_utc": "2026-06-27T21:00:00Z",
            "prediction": "Germany",
            "market_type": "moneyline",
        },
    ]

    collapsed = collapse_to_event_rows(rows)

    assert [row["event"] for row in collapsed] == ["Mexico at Czech Republic", "Germany at Ecuador"]
    assert collapsed[0]["event_duplicate_count"] == 2
    assert collapsed[0]["event_market_count"] == 2


def test_event_duplicate_summary_counts_extra_event_rows():
    rows = [
        {"event": "Australia vs Paraguay", "event_start_utc": "2026-06-27T20:00:00Z", "market_type": "moneyline"},
        {"event": "Australia vs Paraguay", "event_start_utc": "2026-06-27T20:00:00Z", "market_type": "totals"},
        {"event": "Australia vs Paraguay", "event_start_utc": "2026-06-27T20:00:00Z", "market_type": "spread"},
        {"event": "Netherlands vs Tunisia", "event_start_utc": "2026-06-27T21:00:00Z", "market_type": "moneyline"},
    ]

    summary = event_duplicate_summary(rows)

    assert summary == {
        "total_rows": 4,
        "unique_events": 2,
        "duplicate_events": 1,
        "duplicate_event_rows": 2,
    }
