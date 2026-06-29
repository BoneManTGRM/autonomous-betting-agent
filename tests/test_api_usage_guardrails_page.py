import ast
from pathlib import Path

PAGE = Path("pages/api_usage_guardrails.py")
SOURCE = PAGE.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


def _assignment_value(name: str):
    for node in TREE.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"Missing assignment for {name}")


def _text_dict():
    return _assignment_value("TEXT")


def test_api_usage_guardrails_page_imports_read_only_services():
    for token in (
        "build_api_usage_guardrail_report",
        "export_api_usage_guardrail_report_json",
        "validate_api_usage_guardrail_report",
    ):
        assert token in SOURCE


def test_api_usage_guardrails_page_exposes_controls():
    for token in (
        "api_usage_workspace_id",
        "api_usage_tier",
        "api_usage_provider",
        "api_usage_calls",
        "api_usage_cache_hits",
        "api_usage_estimated_cost",
        "api_usage_add_event",
        "api_usage_clear_events",
        "api_usage_run_guardrail",
    ):
        assert token in SOURCE


def test_api_usage_guardrails_page_displays_required_report_fields():
    for token in (
        "schema_version",
        "workspace_id",
        "tier",
        "report_id",
        "report_hash",
        "status",
        "overall_passed",
        "event_count",
        "total_calls",
        "total_billable_calls",
        "cache_hit_rate",
        "estimated_total_cost_usd",
        "provider_results",
        "warning_count",
        "error_count",
    ):
        assert token in SOURCE


def test_api_usage_guardrails_page_has_clear_status_language():
    for token in (
        "API OK",
        "API WARNING",
        "API HIGH USAGE",
        "API BLOCKED",
        "CACHE OK",
        "CACHE WARNING",
        "COST OK",
        "COST WARNING",
    ):
        assert token in SOURCE


def test_api_usage_guardrails_page_download_is_memory_only_and_hash_keyed():
    assert "st.download_button" in SOURCE
    assert "export_api_usage_guardrail_report_json(report, public_safe=True).encode" in SOURCE
    assert "api_usage_guardrail_report_json_{safe_text(report.get('report_hash'))}" in SOURCE
    assert "_report_filename(report)" in SOURCE


def test_api_usage_guardrails_page_uses_in_memory_events_only():
    assert "api_usage_guardrail_events" in SOURCE
    assert "st.session_state" in SOURCE
    assert "write_text" not in SOURCE
    assert "write_bytes" not in SOURCE


def test_api_usage_guardrails_page_has_no_network_or_mutation_paths():
    forbidden = (
        "requests.",
        "httpx.",
        "urllib.",
        "append_performance_rows",
        "sync_rows_by_source",
        "approve_ledger_import",
        "update_result",
        "delete_proof",
        "open(",
    )
    for token in forbidden:
        assert token not in SOURCE


def test_api_usage_guardrails_page_english_and_spanish_text_keys_exist():
    text = _text_dict()
    required = {
        "title",
        "caption",
        "workspace_id",
        "tier",
        "provider",
        "calls",
        "cache_hits",
        "estimated_cost",
        "add_event",
        "clear_events",
        "run_guardrail",
        "event_ready",
        "events_cleared",
        "report_ready",
        "api_ok",
        "api_warning",
        "api_high_usage",
        "api_blocked",
        "cache_ok",
        "cache_warning",
        "cost_ok",
        "cost_warning",
        "usage_events",
        "provider_results",
        "report_summary",
        "validation",
        "download_report",
        "no_report",
    }
    assert required.issubset(text["en"])
    assert required.issubset(text["es"])


def test_api_usage_guardrails_page_has_no_fake_demo_values():
    for token in ("John Doe", "NY Liberty -120", "Aces vs Liberty", "+8.4%"):
        assert token not in SOURCE
