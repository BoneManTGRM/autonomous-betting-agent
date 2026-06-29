import json

from autonomous_betting_agent import api_usage_guardrail_service as usage


def test_normalize_api_provider_aliases_and_unknowns():
    assert usage.normalize_api_provider("odds_api") == "the_odds_api"
    assert usage.normalize_api_provider("Sports Data IO") == "sportsdataio"
    assert usage.normalize_api_provider("weather") == "weatherapi"
    assert usage.normalize_api_provider("px") == "perplexity"
    assert usage.normalize_api_provider("not-real") == "unknown"


def test_normalize_usage_event_calculates_billable_calls_and_cost():
    event = usage.normalize_usage_event({"provider": "the_odds_api", "calls": 1000, "cache_hits": 250})

    assert event["provider"] == "the_odds_api"
    assert event["calls"] == 1000
    assert event["cache_hits"] == 250
    assert event["billable_calls"] == 750
    assert event["estimated_cost_usd"] == 2.625


def test_summarize_api_usage_events_groups_by_provider():
    summary = usage.summarize_api_usage_events([
        {"provider": "the_odds_api", "calls": 100, "cache_hits": 25},
        {"provider": "sportsdataio", "calls": 50, "cache_hits": 10, "estimated_cost_usd": 1.5},
    ])

    assert summary["event_count"] == 2
    assert summary["total_calls"] == 150
    assert summary["total_cache_hits"] == 35
    assert summary["total_billable_calls"] == 115
    assert summary["cache_hit_rate"] == round(35 / 150, 6)
    assert {row["provider"] for row in summary["provider_summaries"]} == {"the_odds_api", "sportsdataio"}


def test_validate_api_usage_limits_passes_clean_usage():
    summary = usage.summarize_api_usage_events([
        {"provider": "weatherapi", "calls": 1000, "cache_hits": 500},
        {"provider": "newsapi", "calls": 1000, "cache_hits": 500},
    ])
    result = usage.validate_api_usage_limits(summary, "pro")

    assert result["passed"] is True
    assert result["status"] == "API OK"


def test_validate_api_usage_limits_warns_on_low_cache_rate():
    summary = usage.summarize_api_usage_events([
        {"provider": "the_odds_api", "calls": 100, "cache_hits": 0},
    ])
    result = usage.validate_api_usage_limits(summary, "pro")

    assert result["passed"] is True
    assert result["status"] == "API WARNING"
    assert "cache hit rate is below tier target" in result["warnings"]


def test_validate_api_usage_limits_blocks_unknown_provider():
    summary = usage.summarize_api_usage_events([
        {"provider": "unknown_vendor", "calls": 10, "cache_hits": 0},
    ])
    result = usage.validate_api_usage_limits(summary, "starter")

    assert result["passed"] is False
    assert result["status"] == "API BLOCKED"
    assert "usage summary contains unknown providers" in result["errors"]


def test_validate_api_usage_limits_high_usage_errors_when_tier_exceeded():
    summary = usage.summarize_api_usage_events([
        {"provider": "the_odds_api", "calls": 40000, "cache_hits": 0},
    ])
    result = usage.validate_api_usage_limits(summary, "starter")

    assert result["passed"] is False
    assert result["status"] in {"API HIGH USAGE", "API BLOCKED"}
    assert any("guardrail" in error for error in result["errors"])


def test_build_api_usage_guardrail_report_includes_required_fields():
    report = usage.build_api_usage_guardrail_report(
        "client-a",
        "starter",
        [{"provider": "weatherapi", "calls": 100, "cache_hits": 50}],
    )

    for field in (
        "schema_version",
        "generated_at_utc",
        "workspace_id",
        "tier",
        "report_id",
        "report_hash",
        "status",
        "overall_passed",
        "total_calls",
        "total_billable_calls",
        "cache_hit_rate",
        "estimated_total_cost_usd",
        "provider_results",
    ):
        assert field in report
    assert report["report_hash"].startswith("api_usage_guardrail_hash_")


def test_api_usage_guardrail_hash_stable_when_generated_at_changes():
    report = usage.build_api_usage_guardrail_report("client-a", "starter", [{"provider": "weatherapi", "calls": 10}])
    changed_time = dict(report, generated_at_utc="2099-01-01T00:00:00Z")
    changed_cost = dict(report, estimated_total_cost_usd=99)

    assert usage.build_api_usage_guardrail_hash(report) == usage.build_api_usage_guardrail_hash(changed_time)
    assert usage.build_api_usage_guardrail_hash(report) != usage.build_api_usage_guardrail_hash(changed_cost)


def test_validate_api_usage_guardrail_report_blocks_overstated_pass():
    report = usage.build_api_usage_guardrail_report("client-a", "starter", [{"provider": "not-real", "calls": 1}])
    overstated = dict(report, overall_passed=True)
    overstated["report_hash"] = usage.build_api_usage_guardrail_hash(overstated)

    result = usage.validate_api_usage_guardrail_report(overstated)

    assert result["passed"] is False
    assert any("overall_passed" in error for error in result["errors"])


def test_sanitized_export_omits_raw_events_and_errors():
    report = usage.build_api_usage_guardrail_report("client-a", "starter", [{"provider": "not-real", "calls": 1}])
    payload = json.loads(usage.export_api_usage_guardrail_report_json(report, public_safe=True))

    assert "events" not in payload
    assert "errors" not in payload
    assert payload["error_count"] >= 1
    assert payload["unknown_provider_count"] == 1


def test_api_usage_guardrail_service_has_no_write_or_network_paths():
    source = open("autonomous_betting_agent/api_usage_guardrail_service.py", encoding="utf-8").read()
    forbidden = (
        "requests.",
        "httpx.",
        "urllib.",
        "append_performance_rows",
        "sync_rows_by_source",
        "approve_ledger_import",
        "write_text",
        "write_bytes",
    )
    for token in forbidden:
        assert token not in source
