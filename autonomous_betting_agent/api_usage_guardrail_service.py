from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

API_USAGE_GUARDRAIL_SCHEMA_VERSION = "api_usage_guardrail_v1"
API_USAGE_PROVIDERS = (
    "the_odds_api",
    "sportsdataio",
    "weatherapi",
    "api_football",
    "perplexity",
    "newsapi",
    "sportradar",
    "exchange_rate",
)
API_USAGE_TIERS = ("starter", "pro", "operator", "enterprise")
API_USAGE_STATUS = ("API OK", "API WARNING", "API HIGH USAGE", "API BLOCKED")
DEFAULT_PROVIDER_LIMITS: dict[str, dict[str, float]] = {
    "the_odds_api": {"monthly_calls": 20000, "monthly_cost_usd": 70.0, "cost_per_1000_calls": 3.50},
    "sportsdataio": {"monthly_calls": 15000, "monthly_cost_usd": 99.0, "cost_per_1000_calls": 6.60},
    "weatherapi": {"monthly_calls": 100000, "monthly_cost_usd": 0.0, "cost_per_1000_calls": 0.0},
    "api_football": {"monthly_calls": 10000, "monthly_cost_usd": 19.0, "cost_per_1000_calls": 1.90},
    "perplexity": {"monthly_calls": 3000, "monthly_cost_usd": 20.0, "cost_per_1000_calls": 6.67},
    "newsapi": {"monthly_calls": 10000, "monthly_cost_usd": 0.0, "cost_per_1000_calls": 0.0},
    "sportradar": {"monthly_calls": 5000, "monthly_cost_usd": 199.0, "cost_per_1000_calls": 39.80},
    "exchange_rate": {"monthly_calls": 10000, "monthly_cost_usd": 0.0, "cost_per_1000_calls": 0.0},
}
TIER_GUARDRAILS: dict[str, dict[str, float]] = {
    "starter": {"monthly_cost_usd": 120.0, "monthly_calls": 30000, "warning_ratio": 0.75, "block_ratio": 1.0, "min_cache_hit_rate": 0.25},
    "pro": {"monthly_cost_usd": 300.0, "monthly_calls": 90000, "warning_ratio": 0.80, "block_ratio": 1.0, "min_cache_hit_rate": 0.35},
    "operator": {"monthly_cost_usd": 750.0, "monthly_calls": 250000, "warning_ratio": 0.85, "block_ratio": 1.0, "min_cache_hit_rate": 0.45},
    "enterprise": {"monthly_cost_usd": 2500.0, "monthly_calls": 1000000, "warning_ratio": 0.90, "block_ratio": 1.0, "min_cache_hit_rate": 0.55},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _canonical_dumps(value: Any) -> str:
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash_payload(prefix: str, payload: Mapping[str, Any], length: int = 32) -> str:
    return f"{prefix}_{hashlib.sha256(_canonical_dumps(payload).encode('utf-8')).hexdigest()[:length]}"


def normalize_api_provider(provider: str | None) -> str:
    value = str(provider or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "odds_api": "the_odds_api",
        "theoddsapi": "the_odds_api",
        "sportsdata": "sportsdataio",
        "sports_data_io": "sportsdataio",
        "weather": "weatherapi",
        "api_football_com": "api_football",
        "football_api": "api_football",
        "px": "perplexity",
        "news": "newsapi",
        "exchange": "exchange_rate",
        "exchange_rates": "exchange_rate",
    }
    normalized = aliases.get(value, value)
    return normalized if normalized in API_USAGE_PROVIDERS else "unknown"


def normalize_usage_tier(tier: str | None) -> str:
    value = str(tier or "starter").strip().lower().replace(" ", "_")
    aliases = {"basic": "starter", "standard": "pro", "ops": "operator", "business": "enterprise"}
    normalized = aliases.get(value, value)
    return normalized if normalized in API_USAGE_TIERS else "starter"


def normalize_usage_event(event: Mapping[str, Any]) -> dict[str, Any]:
    provider = normalize_api_provider(event.get("provider") or event.get("api_provider") or event.get("source"))
    calls = max(0, int(float(event.get("calls", event.get("call_count", 1)) or 0)))
    cache_hits = max(0, int(float(event.get("cache_hits", event.get("cached_calls", 0)) or 0)))
    cache_hits = min(cache_hits, calls)
    explicit_cost = event.get("estimated_cost_usd", event.get("cost_usd"))
    provider_limits = DEFAULT_PROVIDER_LIMITS.get(provider, {"cost_per_1000_calls": 0.0})
    estimated_cost = float(explicit_cost) if explicit_cost not in (None, "") else (calls - cache_hits) * float(provider_limits.get("cost_per_1000_calls", 0.0)) / 1000.0
    return {
        "workspace_id": str(event.get("workspace_id") or "default"),
        "provider": provider,
        "endpoint": str(event.get("endpoint") or event.get("route") or "unknown"),
        "calls": calls,
        "cache_hits": cache_hits,
        "billable_calls": max(0, calls - cache_hits),
        "estimated_cost_usd": round(max(0.0, estimated_cost), 6),
        "status_code": str(event.get("status_code") or ""),
        "created_at_utc": str(event.get("created_at_utc") or ""),
    }


def summarize_api_usage_events(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized = [normalize_usage_event(event) for event in events or []]
    by_provider: dict[str, dict[str, Any]] = {}
    total_calls = 0
    total_billable_calls = 0
    total_cache_hits = 0
    total_cost = 0.0
    unknown_provider_count = 0
    for event in normalized:
        provider = event["provider"]
        if provider == "unknown":
            unknown_provider_count += 1
        row = by_provider.setdefault(provider, {"provider": provider, "calls": 0, "billable_calls": 0, "cache_hits": 0, "estimated_cost_usd": 0.0, "event_count": 0})
        row["calls"] += int(event["calls"])
        row["billable_calls"] += int(event["billable_calls"])
        row["cache_hits"] += int(event["cache_hits"])
        row["estimated_cost_usd"] = round(float(row["estimated_cost_usd"]) + float(event["estimated_cost_usd"]), 6)
        row["event_count"] += 1
        total_calls += int(event["calls"])
        total_billable_calls += int(event["billable_calls"])
        total_cache_hits += int(event["cache_hits"])
        total_cost += float(event["estimated_cost_usd"])
    cache_hit_rate = (total_cache_hits / total_calls) if total_calls else 0.0
    return {
        "events": normalized,
        "provider_summaries": sorted(by_provider.values(), key=lambda row: row["provider"]),
        "event_count": len(normalized),
        "total_calls": total_calls,
        "total_billable_calls": total_billable_calls,
        "total_cache_hits": total_cache_hits,
        "cache_hit_rate": round(cache_hit_rate, 6),
        "estimated_total_cost_usd": round(total_cost, 6),
        "unknown_provider_count": unknown_provider_count,
    }


def validate_api_usage_limits(summary: Mapping[str, Any], tier: str = "starter", provider_limits: Mapping[str, Mapping[str, float]] | None = None) -> dict[str, Any]:
    selected_tier = normalize_usage_tier(tier)
    tier_limits = TIER_GUARDRAILS[selected_tier]
    limits = provider_limits or DEFAULT_PROVIDER_LIMITS
    warnings: list[str] = []
    errors: list[str] = []
    provider_results: list[dict[str, Any]] = []
    total_calls = int(summary.get("total_calls") or 0)
    total_cost = float(summary.get("estimated_total_cost_usd") or 0.0)
    cache_hit_rate = float(summary.get("cache_hit_rate") or 0.0)

    for row in summary.get("provider_summaries") or []:
        provider = row.get("provider")
        provider_limit = limits.get(provider, {"monthly_calls": 0, "monthly_cost_usd": 0.0})
        monthly_calls_limit = int(provider_limit.get("monthly_calls", 0) or 0)
        monthly_cost_limit = float(provider_limit.get("monthly_cost_usd", 0.0) or 0.0)
        calls_used = int(row.get("calls") or 0)
        cost_used = float(row.get("estimated_cost_usd") or 0.0)
        call_ratio = calls_used / monthly_calls_limit if monthly_calls_limit else (1.0 if calls_used else 0.0)
        cost_ratio = cost_used / monthly_cost_limit if monthly_cost_limit else (1.0 if cost_used else 0.0)
        provider_status = "API OK"
        if provider == "unknown":
            provider_status = "API BLOCKED"
            errors.append("unknown API provider detected")
        elif call_ratio >= 1.0 or cost_ratio >= 1.0:
            provider_status = "API HIGH USAGE"
            errors.append(f"{provider} exceeded provider monthly guardrail")
        elif call_ratio >= float(tier_limits["warning_ratio"]) or cost_ratio >= float(tier_limits["warning_ratio"]):
            provider_status = "API WARNING"
            warnings.append(f"{provider} is approaching provider monthly guardrail")
        provider_results.append({
            "provider": provider,
            "calls_used": calls_used,
            "call_limit": monthly_calls_limit,
            "call_ratio": round(call_ratio, 6),
            "estimated_cost_usd": round(cost_used, 6),
            "cost_limit_usd": monthly_cost_limit,
            "cost_ratio": round(cost_ratio, 6),
            "status": provider_status,
        })

    total_call_ratio = total_calls / float(tier_limits["monthly_calls"] or 1)
    total_cost_ratio = total_cost / float(tier_limits["monthly_cost_usd"] or 1)
    if total_call_ratio >= float(tier_limits["block_ratio"]) or total_cost_ratio >= float(tier_limits["block_ratio"]):
        errors.append("workspace exceeded tier monthly guardrail")
    elif total_call_ratio >= float(tier_limits["warning_ratio"]) or total_cost_ratio >= float(tier_limits["warning_ratio"]):
        warnings.append("workspace is approaching tier monthly guardrail")
    if cache_hit_rate < float(tier_limits["min_cache_hit_rate"]) and total_calls > 0:
        warnings.append("cache hit rate is below tier target")
    if int(summary.get("unknown_provider_count") or 0) > 0:
        errors.append("usage summary contains unknown providers")

    status = "API OK"
    if errors:
        status = "API BLOCKED" if any("unknown" in error.lower() for error in errors) else "API HIGH USAGE"
    elif warnings:
        status = "API WARNING"

    return {
        "passed": not errors,
        "status": status,
        "tier": selected_tier,
        "checked_outputs": ["tier_guardrails", "provider_guardrails", "cache_hit_rate", "unknown_providers"],
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
        "details": {
            "total_call_ratio": round(total_call_ratio, 6),
            "total_cost_ratio": round(total_cost_ratio, 6),
            "min_cache_hit_rate": tier_limits["min_cache_hit_rate"],
            "provider_results": provider_results,
        },
    }


def build_api_usage_guardrail_report(workspace_id: str | None = None, tier: str = "starter", events: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    selected_workspace = str(workspace_id or "default")
    selected_tier = normalize_usage_tier(tier)
    summary = summarize_api_usage_events(events or [])
    validation = validate_api_usage_limits(summary, selected_tier)
    report = {
        "schema_version": API_USAGE_GUARDRAIL_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "workspace_id": selected_workspace,
        "tier": selected_tier,
        "report_id": "",
        "report_hash": "",
        "status": validation["status"],
        "overall_passed": validation["passed"],
        "event_count": summary["event_count"],
        "total_calls": summary["total_calls"],
        "total_billable_calls": summary["total_billable_calls"],
        "total_cache_hits": summary["total_cache_hits"],
        "cache_hit_rate": summary["cache_hit_rate"],
        "estimated_total_cost_usd": summary["estimated_total_cost_usd"],
        "unknown_provider_count": summary["unknown_provider_count"],
        "provider_summaries": summary["provider_summaries"],
        "provider_results": (validation.get("details") or {}).get("provider_results", []),
        "tier_limits": TIER_GUARDRAILS[selected_tier],
        "checked_outputs": validation["checked_outputs"],
        "warnings": validation["warnings"],
        "errors": validation["errors"],
    }
    report["report_id"] = _hash_payload("api_usage_guardrail", {
        "workspace_id": selected_workspace,
        "tier": selected_tier,
        "events": summary["events"],
    }, length=24)
    report["report_hash"] = build_api_usage_guardrail_hash(report)
    return report


def build_api_usage_guardrail_hash(report: Mapping[str, Any]) -> str:
    stable = {key: value for key, value in dict(report).items() if key not in {"generated_at_utc", "report_hash"}}
    return _hash_payload("api_usage_guardrail_hash", stable)


def validate_api_usage_guardrail_report(report: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    required = (
        "schema_version",
        "workspace_id",
        "tier",
        "report_id",
        "report_hash",
        "status",
        "overall_passed",
        "total_calls",
        "estimated_total_cost_usd",
        "cache_hit_rate",
        "provider_results",
    )
    for field in required:
        if field not in report:
            errors.append(f"missing field: {field}")
    if report.get("schema_version") != API_USAGE_GUARDRAIL_SCHEMA_VERSION:
        errors.append("unsupported api usage guardrail schema_version")
    if report.get("status") not in API_USAGE_STATUS:
        errors.append("unsupported API usage status")
    if report.get("report_hash") and build_api_usage_guardrail_hash(report) != report.get("report_hash"):
        errors.append("report_hash does not match report contents")
    if report.get("overall_passed") and report.get("errors"):
        errors.append("overall_passed is overstated")
    if report.get("overall_passed") and report.get("status") in {"API HIGH USAGE", "API BLOCKED"}:
        errors.append("overall_passed conflicts with API usage status")
    return {
        "passed": not errors,
        "checked_outputs": ["schema_version", "report_hash", "status", "overall_passed"],
        "warnings": [],
        "errors": errors,
        "details": {"rebuilt_report_hash": build_api_usage_guardrail_hash(report) if report.get("report_hash") else ""},
    }


def sanitize_api_usage_guardrail_report(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report.get("schema_version"),
        "workspace_id": report.get("workspace_id"),
        "tier": report.get("tier"),
        "report_id": report.get("report_id"),
        "report_hash": report.get("report_hash"),
        "status": report.get("status"),
        "overall_passed": report.get("overall_passed"),
        "event_count": report.get("event_count", 0),
        "total_calls": report.get("total_calls", 0),
        "total_billable_calls": report.get("total_billable_calls", 0),
        "total_cache_hits": report.get("total_cache_hits", 0),
        "cache_hit_rate": report.get("cache_hit_rate", 0.0),
        "estimated_total_cost_usd": report.get("estimated_total_cost_usd", 0.0),
        "unknown_provider_count": report.get("unknown_provider_count", 0),
        "provider_results": report.get("provider_results", []),
        "warning_count": len(report.get("warnings") or []),
        "error_count": len(report.get("errors") or []),
    }


def export_api_usage_guardrail_report_json(report: Mapping[str, Any], *, public_safe: bool = True) -> str:
    payload = sanitize_api_usage_guardrail_report(report) if public_safe else dict(report)
    return json.dumps(_json_safe(payload), sort_keys=True, indent=2)
