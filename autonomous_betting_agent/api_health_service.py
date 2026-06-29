from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

API_HEALTH_SCHEMA_VERSION = "api_health_v1"
API_HEALTH_PROVIDERS = (
    "the_odds_api",
    "sportsdataio",
    "weatherapi",
    "api_football",
    "perplexity",
    "newsapi",
    "sportradar",
    "exchange_rate",
)
API_HEALTH_STATUSES = (
    "API OK",
    "API DEGRADED",
    "API STALE",
    "API DOWN",
    "FALLBACK ACTIVE",
    "REPORT NOT DATA-COMPLETE",
)
DEFAULT_STALE_LIMIT_MINUTES = {
    "the_odds_api": 15,
    "sportsdataio": 60,
    "weatherapi": 180,
    "api_football": 60,
    "perplexity": 720,
    "newsapi": 720,
    "sportradar": 60,
    "exchange_rate": 1440,
}
DEFAULT_LATENCY_WARNING_MS = 3500


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


def normalize_api_health_provider(provider: str | None) -> str:
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
    return normalized if normalized in API_HEALTH_PROVIDERS else "unknown"


def normalize_api_health_event(event: Mapping[str, Any]) -> dict[str, Any]:
    provider = normalize_api_health_provider(event.get("provider") or event.get("api_provider") or event.get("source"))
    status_code = int(float(event.get("status_code") or event.get("http_status") or 0))
    success_count = max(0, int(float(event.get("success_count", event.get("successes", 0)) or 0)))
    error_count = max(0, int(float(event.get("error_count", event.get("errors", 0)) or 0)))
    records_count = max(0, int(float(event.get("records_count", event.get("rows", event.get("records", 0))) or 0)))
    latency_ms = max(0, int(float(event.get("latency_ms", event.get("response_ms", 0)) or 0)))
    data_age_minutes = max(0.0, float(event.get("data_age_minutes", event.get("age_minutes", 0.0)) or 0.0))
    fallback_active = bool(event.get("fallback_active") or event.get("fallback_used") or event.get("using_fallback"))
    context_available = bool(event.get("context_available", True))
    odds_available = bool(event.get("odds_available", True))
    return {
        "workspace_id": str(event.get("workspace_id") or "default"),
        "provider": provider,
        "endpoint": str(event.get("endpoint") or event.get("route") or "unknown"),
        "status_code": status_code,
        "success_count": success_count,
        "error_count": error_count,
        "records_count": records_count,
        "latency_ms": latency_ms,
        "data_age_minutes": round(data_age_minutes, 6),
        "fallback_active": fallback_active,
        "context_available": context_available,
        "odds_available": odds_available,
        "last_success_at_utc": str(event.get("last_success_at_utc") or ""),
        "checked_at_utc": str(event.get("checked_at_utc") or event.get("created_at_utc") or ""),
    }


def classify_api_health_event(event: Mapping[str, Any], stale_limits: Mapping[str, float] | None = None) -> dict[str, Any]:
    normalized = normalize_api_health_event(event)
    stale_map = stale_limits or DEFAULT_STALE_LIMIT_MINUTES
    provider = normalized["provider"]
    stale_limit = float(stale_map.get(provider, 60))
    reasons: list[str] = []
    status = "API OK"
    data_complete = True

    if provider == "unknown":
        status = "API DOWN"
        reasons.append("unknown provider")
        data_complete = False
    elif normalized["status_code"] >= 500 or (normalized["error_count"] > 0 and normalized["success_count"] == 0):
        status = "API DOWN"
        reasons.append("provider unavailable or all checks failed")
        data_complete = False
    elif normalized["fallback_active"]:
        status = "FALLBACK ACTIVE"
        reasons.append("fallback data is active")
        data_complete = False
    elif normalized["data_age_minutes"] > stale_limit:
        status = "API STALE"
        reasons.append("data age exceeds stale threshold")
        data_complete = False
    elif normalized["status_code"] >= 400 or normalized["error_count"] > 0 or normalized["latency_ms"] > DEFAULT_LATENCY_WARNING_MS or not normalized["context_available"] or not normalized["odds_available"]:
        status = "API DEGRADED"
        reasons.append("provider degraded, slow, missing odds, or missing context")
        data_complete = False

    result = dict(normalized)
    result.update({
        "status": status,
        "stale_limit_minutes": stale_limit,
        "data_complete": data_complete,
        "reasons": reasons,
    })
    return result


def summarize_api_health_events(events: Sequence[Mapping[str, Any]], stale_limits: Mapping[str, float] | None = None) -> dict[str, Any]:
    classified = [classify_api_health_event(event, stale_limits) for event in events or []]
    provider_results: dict[str, dict[str, Any]] = {}
    for event in classified:
        provider = event["provider"]
        row = provider_results.setdefault(provider, {
            "provider": provider,
            "status": "API OK",
            "check_count": 0,
            "down_count": 0,
            "stale_count": 0,
            "degraded_count": 0,
            "fallback_count": 0,
            "data_complete": True,
            "max_data_age_minutes": 0.0,
            "max_latency_ms": 0,
            "records_count": 0,
            "reason_count": 0,
        })
        row["check_count"] += 1
        row["max_data_age_minutes"] = max(float(row["max_data_age_minutes"]), float(event["data_age_minutes"]))
        row["max_latency_ms"] = max(int(row["max_latency_ms"]), int(event["latency_ms"]))
        row["records_count"] += int(event["records_count"])
        row["reason_count"] += len(event.get("reasons") or [])
        if event["status"] == "API DOWN":
            row["down_count"] += 1
        if event["status"] == "API STALE":
            row["stale_count"] += 1
        if event["status"] == "API DEGRADED":
            row["degraded_count"] += 1
        if event["status"] == "FALLBACK ACTIVE":
            row["fallback_count"] += 1
        if not event["data_complete"]:
            row["data_complete"] = False
        row["status"] = _rollup_status(row)
    return {
        "events": classified,
        "provider_results": sorted(provider_results.values(), key=lambda row: row["provider"]),
        "check_count": len(classified),
        "provider_count": len(provider_results),
        "down_provider_count": len([row for row in provider_results.values() if row["status"] == "API DOWN"]),
        "stale_provider_count": len([row for row in provider_results.values() if row["status"] == "API STALE"]),
        "fallback_provider_count": len([row for row in provider_results.values() if row["status"] == "FALLBACK ACTIVE"]),
        "degraded_provider_count": len([row for row in provider_results.values() if row["status"] == "API DEGRADED"]),
        "data_complete": all(row["data_complete"] for row in provider_results.values()) if provider_results else False,
    }


def _rollup_status(row: Mapping[str, Any]) -> str:
    if int(row.get("down_count") or 0) > 0:
        return "API DOWN"
    if int(row.get("fallback_count") or 0) > 0:
        return "FALLBACK ACTIVE"
    if int(row.get("stale_count") or 0) > 0:
        return "API STALE"
    if int(row.get("degraded_count") or 0) > 0:
        return "API DEGRADED"
    return "API OK"


def _report_status(summary: Mapping[str, Any]) -> str:
    if int(summary.get("down_provider_count") or 0) > 0:
        return "API DOWN"
    if int(summary.get("fallback_provider_count") or 0) > 0:
        return "FALLBACK ACTIVE"
    if int(summary.get("stale_provider_count") or 0) > 0:
        return "API STALE"
    if int(summary.get("degraded_provider_count") or 0) > 0:
        return "API DEGRADED"
    if summary.get("data_complete"):
        return "API OK"
    return "REPORT NOT DATA-COMPLETE"


def build_api_health_report(workspace_id: str | None = None, events: Sequence[Mapping[str, Any]] | None = None, stale_limits: Mapping[str, float] | None = None) -> dict[str, Any]:
    selected_workspace = str(workspace_id or "default")
    summary = summarize_api_health_events(events or [], stale_limits)
    status = _report_status(summary)
    warnings: list[str] = []
    errors: list[str] = []
    if status in {"API DEGRADED", "API STALE", "FALLBACK ACTIVE", "REPORT NOT DATA-COMPLETE"}:
        warnings.append("API/data health is not fully complete")
    if status == "API DOWN":
        errors.append("one or more providers are down")
    if not summary.get("data_complete"):
        warnings.append("report data is not complete")
    report = {
        "schema_version": API_HEALTH_SCHEMA_VERSION,
        "generated_at_utc": _utc_now(),
        "workspace_id": selected_workspace,
        "report_id": "",
        "report_hash": "",
        "status": status,
        "overall_passed": status in {"API OK", "API DEGRADED"},
        "data_complete": bool(summary.get("data_complete")),
        "check_count": summary["check_count"],
        "provider_count": summary["provider_count"],
        "down_provider_count": summary["down_provider_count"],
        "stale_provider_count": summary["stale_provider_count"],
        "fallback_provider_count": summary["fallback_provider_count"],
        "degraded_provider_count": summary["degraded_provider_count"],
        "provider_results": summary["provider_results"],
        "checked_outputs": ["provider_status", "stale_data", "fallback_active", "data_complete", "report_status"],
        "warnings": sorted(set(warnings)),
        "errors": sorted(set(errors)),
    }
    report["report_id"] = _hash_payload("api_health", {"workspace_id": selected_workspace, "events": summary["events"]}, length=24)
    report["report_hash"] = build_api_health_report_hash(report)
    return report


def build_api_health_report_hash(report: Mapping[str, Any]) -> str:
    stable = {key: value for key, value in dict(report).items() if key not in {"generated_at_utc", "report_hash"}}
    return _hash_payload("api_health_hash", stable)


def validate_api_health_report(report: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    required = (
        "schema_version",
        "workspace_id",
        "report_id",
        "report_hash",
        "status",
        "overall_passed",
        "data_complete",
        "check_count",
        "provider_results",
    )
    for field in required:
        if field not in report:
            errors.append(f"missing field: {field}")
    if report.get("schema_version") != API_HEALTH_SCHEMA_VERSION:
        errors.append("unsupported api health schema_version")
    if report.get("status") not in API_HEALTH_STATUSES:
        errors.append("unsupported API health status")
    if report.get("report_hash") and build_api_health_report_hash(report) != report.get("report_hash"):
        errors.append("report_hash does not match report contents")
    if report.get("overall_passed") and report.get("status") in {"API DOWN", "API STALE", "FALLBACK ACTIVE", "REPORT NOT DATA-COMPLETE"}:
        errors.append("overall_passed is overstated for current API health status")
    if report.get("data_complete") and (report.get("down_provider_count") or report.get("stale_provider_count") or report.get("fallback_provider_count")):
        errors.append("data_complete is overstated")
    return {
        "passed": not errors,
        "checked_outputs": ["schema_version", "report_hash", "status", "overall_passed", "data_complete"],
        "warnings": [],
        "errors": errors,
        "details": {"rebuilt_report_hash": build_api_health_report_hash(report) if report.get("report_hash") else ""},
    }


def sanitize_api_health_report(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": report.get("schema_version"),
        "workspace_id": report.get("workspace_id"),
        "report_id": report.get("report_id"),
        "report_hash": report.get("report_hash"),
        "status": report.get("status"),
        "overall_passed": report.get("overall_passed"),
        "data_complete": report.get("data_complete"),
        "check_count": report.get("check_count", 0),
        "provider_count": report.get("provider_count", 0),
        "down_provider_count": report.get("down_provider_count", 0),
        "stale_provider_count": report.get("stale_provider_count", 0),
        "fallback_provider_count": report.get("fallback_provider_count", 0),
        "degraded_provider_count": report.get("degraded_provider_count", 0),
        "provider_results": report.get("provider_results", []),
        "warning_count": len(report.get("warnings") or []),
        "error_count": len(report.get("errors") or []),
    }


def export_api_health_report_json(report: Mapping[str, Any], *, public_safe: bool = True) -> str:
    payload = sanitize_api_health_report(report) if public_safe else dict(report)
    return json.dumps(_json_safe(payload), sort_keys=True, indent=2)
