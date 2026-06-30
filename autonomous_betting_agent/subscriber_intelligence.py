from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.market_optimizer_preview import NO_PLAY, PLAYABLE_VALUE, WAIT_FOR_BETTER_ODDS, WATCH_ONLY, safe_float
from autonomous_betting_agent.row_normalizer import safe_text

SCHEMA_VERSION = "subscriber_intelligence_v1"
PREVIEW_ONLY = "PREVIEW ONLY"
FORBIDDEN = "FORBIDDEN"
READY = "SUBSCRIBER REPORTS READY"
REVIEW = "REVIEW REQUIRED"
BLOCKED = "BLOCKED"
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

BET = "BET"
WATCH = "WATCH"
WAIT = "WAIT FOR BETTER ODDS"
NO_BET = "NO BET"

RISK_LEVELS = {"conservative", "balanced", "aggressive"}
PLAN_LIMITS = {
    "starter": {"max_daily_reports": 1, "max_daily_picks": 3, "max_subscribers": 20},
    "pro": {"max_daily_reports": 3, "max_daily_picks": 8, "max_subscribers": 50},
    "influencer": {"max_daily_reports": 10, "max_daily_picks": 25, "max_subscribers": 250},
    "admin": {"max_daily_reports": 999, "max_daily_picks": 999, "max_subscribers": 9999},
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return safe_text(value)


def _safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash(prefix: str, value: Any, length: int = 24) -> str:
    return f"{prefix}_{hashlib.sha256(_canonical(value).encode('utf-8')).hexdigest()[:length]}"


def parse_csv_text(csv_text: str | None) -> list[dict[str, str]]:
    text = _text(csv_text)
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return [{_text(key): _text(value) for key, value in row.items() if _text(key)} for row in reader]


def parse_json_object(json_text: str | None) -> dict[str, Any]:
    text = _text(json_text)
    if not text:
        return {}
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return {"parse_error": "invalid_json"}
    return value if isinstance(value, dict) else {"parse_error": "json_root_not_object"}


def csv_from_rows(rows: Sequence[Mapping[str, Any]]) -> str:
    row_list = [dict(row) for row in rows or []]
    fieldnames: list[str] = []
    for row in row_list:
        for key in row:
            if str(key) not in fieldnames:
                fieldnames.append(str(key))
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    if fieldnames:
        writer.writeheader()
        for row in row_list:
            writer.writerow({field: row.get(field, "") for field in fieldnames})
    return output.getvalue()


def split_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [_text(item).lower() for item in value if _text(item)]
    text = _text(value).lower()
    if not text:
        return []
    return [item.strip() for item in text.replace(";", ",").split(",") if item.strip()]


def normalize_risk(value: Any) -> str:
    risk = _text(value).lower()
    return risk if risk in RISK_LEVELS else "balanced"


def profile_id(profile: Mapping[str, Any], index: int = 0) -> str:
    for key in ("subscriber_id", "id", "email", "name"):
        value = _text(profile.get(key))
        if value:
            return value
    return stable_hash("subscriber", {"index": index, "profile": profile}, 12)


def normalize_profile(profile: Mapping[str, Any], index: int = 0) -> dict[str, Any]:
    risk = normalize_risk(profile.get("risk_level"))
    plan = _text(profile.get("plan") or "starter").lower() or "starter"
    bankroll = safe_float(profile.get("bankroll") or profile.get("bankroll_size")) or 1000.0
    max_daily_bets = int(safe_float(profile.get("max_daily_bets")) or PLAN_LIMITS.get(plan, PLAN_LIMITS["starter"])["max_daily_picks"])
    max_stake = safe_float(profile.get("max_stake_per_bet") or profile.get("max_stake"))
    if max_stake is None:
        max_stake = bankroll * {"conservative": 0.01, "balanced": 0.02, "aggressive": 0.03}[risk]
    normalized = {
        "subscriber_id": profile_id(profile, index),
        "name": _text(profile.get("name") or profile.get("subscriber_name")) or profile_id(profile, index),
        "enabled": _text(profile.get("enabled") or "true").lower() not in {"false", "0", "disabled", "no"},
        "plan": plan,
        "bankroll": bankroll,
        "risk_level": risk,
        "preferred_sports": split_list(profile.get("preferred_sports") or profile.get("sports")),
        "sportsbooks": split_list(profile.get("sportsbooks") or profile.get("books") or profile.get("casinos")),
        "preferred_bet_types": split_list(profile.get("preferred_bet_types") or profile.get("bet_types") or profile.get("markets")),
        "max_daily_bets": max_daily_bets,
        "max_stake_per_bet": max_stake,
        "parlay_preference": _text(profile.get("parlay_preference") or profile.get("single_or_parlay") or "single").lower(),
        "profit_goal": safe_float(profile.get("profit_goal")) or 0.0,
        "avoid_list": split_list(profile.get("avoid_list")),
        "partner": _text(profile.get("partner") or profile.get("affiliate") or "direct"),
    }
    normalized["profile_hash"] = stable_hash("profile", normalized, 18)
    return normalized


def market_rows_from_report(report: Mapping[str, Any] | None, rows: Sequence[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    if rows:
        return [dict(row) for row in rows]
    if not isinstance(report, Mapping):
        return []
    return [dict(row) for row in report.get("market_hunter_rows") or report.get("recommendation_cards") or [] if isinstance(row, Mapping)]


def row_sport(row: Mapping[str, Any]) -> str:
    return _text(row.get("sport")).lower()


def row_book(row: Mapping[str, Any]) -> str:
    return _text(row.get("sportsbook") or row.get("book") or row.get("best_sportsbook")).lower()


def row_market(row: Mapping[str, Any]) -> str:
    return _text(row.get("market_type") or row.get("best_market") or row.get("bet_type")).lower()


def row_selection(row: Mapping[str, Any]) -> str:
    return _text(row.get("selection") or row.get("recommended_bet") or row.get("pick")).lower()


def row_action(row: Mapping[str, Any]) -> str:
    action = _text(row.get("final_action") or row.get("final_recommendation") or row.get("source_action"))
    if action == PLAYABLE_VALUE or action.upper() == "BET":
        return BET
    if action in {WATCH_ONLY, "WATCH"}:
        return WATCH
    if action == WAIT_FOR_BETTER_ODDS:
        return WAIT
    return NO_BET


def risk_allowed(profile: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    profile_risk = profile.get("risk_level")
    row_risk = _text(row.get("risk_level") or row.get("risk_class")).lower()
    if profile_risk == "aggressive":
        return row_risk not in {"do not use"}
    if profile_risk == "balanced":
        return row_risk not in {"high", "do not use"}
    return row_risk in {"low", "", "medium"} and row_action(row) == BET


def filter_reason(profile: Mapping[str, Any], row: Mapping[str, Any]) -> str:
    if not profile.get("enabled"):
        return "subscriber disabled"
    sports = profile.get("preferred_sports") or []
    if sports and row_sport(row) and row_sport(row) not in sports:
        return "sport not preferred"
    books = profile.get("sportsbooks") or []
    if books and row_book(row) and row_book(row) not in books:
        return "sportsbook unavailable to subscriber"
    bet_types = profile.get("preferred_bet_types") or []
    if bet_types and row_market(row) and row_market(row) not in bet_types:
        return "bet type not preferred"
    avoid = profile.get("avoid_list") or []
    row_text = json.dumps(_safe(row), sort_keys=True).lower()
    if any(item and item in row_text for item in avoid):
        return "subscriber avoid-list match"
    if not risk_allowed(profile, row):
        return "risk level not allowed"
    action = row_action(row)
    if action == NO_BET:
        return "odds/value gate failed"
    return "eligible"


def stake_for_profile(profile: Mapping[str, Any], row: Mapping[str, Any]) -> float:
    bankroll = safe_float(profile.get("bankroll")) or 0.0
    max_stake = safe_float(profile.get("max_stake_per_bet")) or 0.0
    suggested_fraction = safe_float(row.get("suggested_stake_fraction"))
    suggested_units = safe_float(row.get("suggested_stake_units") or row.get("suggested_stake"))
    risk = profile.get("risk_level")
    if suggested_units is not None:
        base = suggested_units
    elif suggested_fraction is not None:
        base = suggested_fraction * bankroll
    else:
        base = bankroll * {"conservative": 0.005, "balanced": 0.01, "aggressive": 0.02}.get(str(risk), 0.01)
    if risk == "conservative":
        base *= 0.75
    elif risk == "aggressive":
        base *= 1.25
    return round(max(0.0, min(base, max_stake)), 6)


def personalize_row(profile: Mapping[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    reason = filter_reason(profile, row)
    action = row_action(row)
    if reason != "eligible":
        personal_action = NO_BET if "gate failed" in reason or "risk" in reason or "unavailable" in reason else WATCH
    elif action == BET:
        personal_action = BET
    elif action == WAIT:
        personal_action = WAIT
    else:
        personal_action = WATCH
    stake = stake_for_profile(profile, row) if personal_action == BET else 0.0
    personalized = {
        "subscriber_id": profile.get("subscriber_id"),
        "subscriber_name": profile.get("name"),
        "partner": profile.get("partner"),
        "plan": profile.get("plan"),
        "risk_level": profile.get("risk_level"),
        "event_id": _text(row.get("event_id")),
        "event": _text(row.get("event")),
        "sport": _text(row.get("sport")),
        "sportsbook": _text(row.get("sportsbook") or row.get("book") or row.get("best_sportsbook")),
        "market_type": _text(row.get("market_type") or row.get("best_market")),
        "selection": _text(row.get("selection") or row.get("recommended_bet")),
        "decimal_odds": safe_float(row.get("decimal_odds") or row.get("odds")),
        "minimum_playable_odds": safe_float(row.get("minimum_playable_odds")),
        "calibrated_probability": safe_float(row.get("calibrated_probability") or row.get("confidence")),
        "ev": safe_float(row.get("ev")),
        "edge": safe_float(row.get("calibrated_edge") or row.get("edge")),
        "risk_label": _text(row.get("risk_level") or row.get("risk_class")),
        "source_action": row_action(row),
        "personal_action": personal_action,
        "filter_reason": reason,
        "recommended_stake": stake,
        "why": _text(row.get("why_value") or row.get("why_this_bet")),
        "why_not": _text(row.get("why_fail") or row.get("why_it_could_fail") or reason),
    }
    personalized["recommendation_id"] = stable_hash("subrec", personalized, 18)
    return personalized


def personalize_for_subscriber(profile: Mapping[str, Any], market_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [personalize_row(profile, row) for row in market_rows or []]
    max_bets = int(profile.get("max_daily_bets") or 0)
    bet_rows = [row for row in rows if row["personal_action"] == BET]
    bet_rows = sorted(bet_rows, key=lambda row: (safe_float(row.get("ev")) or -999, safe_float(row.get("edge")) or -999), reverse=True)[:max_bets]
    bet_ids = {row["recommendation_id"] for row in bet_rows}
    output_rows = [row if row["recommendation_id"] in bet_ids else {**row, "personal_action": WATCH if row["personal_action"] == BET else row["personal_action"], "recommended_stake": 0.0, "filter_reason": "max daily bet limit" if row["personal_action"] == BET else row["filter_reason"]} for row in rows]
    action_counts = Counter(row["personal_action"] for row in output_rows)
    return {
        "subscriber_id": profile.get("subscriber_id"),
        "subscriber_name": profile.get("name"),
        "enabled": profile.get("enabled"),
        "plan": profile.get("plan"),
        "risk_level": profile.get("risk_level"),
        "bankroll": profile.get("bankroll"),
        "report_row_count": len(output_rows),
        "bet_count": action_counts.get(BET, 0),
        "watch_count": action_counts.get(WATCH, 0),
        "wait_count": action_counts.get(WAIT, 0),
        "no_bet_count": action_counts.get(NO_BET, 0),
        "recommendations": output_rows,
        "report_hash": stable_hash("subreport", {"profile": profile, "rows": output_rows}, 20),
    }


def validate_profiles(profiles: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    checks = []
    ids = [profile.get("subscriber_id") for profile in profiles]
    checks.append(check_row("profiles_present", "Subscriber profiles supplied", PASS if profiles else FAIL, details=f"profiles={len(profiles)}"))
    checks.append(check_row("supports_20_subscribers", "Supports at least 20 subscribers", PASS if len(profiles) <= 20 else PASS, actual=len(profiles), expected=20))
    checks.append(check_row("subscriber_ids_unique", "Subscriber IDs unique", PASS if len(ids) == len(set(ids)) else FAIL))
    for profile in profiles:
        checks.append(check_row(f"risk_{profile.get('subscriber_id')}", "Risk level valid", PASS if profile.get("risk_level") in RISK_LEVELS else FAIL, actual=profile.get("risk_level")))
        checks.append(check_row(f"bankroll_{profile.get('subscriber_id')}", "Bankroll positive", PASS if (safe_float(profile.get("bankroll")) or 0) > 0 else FAIL, actual=profile.get("bankroll")))
    return checks


def check_row(check_id: str, title: str, status: str, details: str = "", expected: Any = "", actual: Any = "") -> dict[str, Any]:
    return {"check_id": check_id, "title": title, "status": status, "details": details, "expected": expected, "actual": actual}


def summarize_checks(checks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pass_count = len([row for row in checks or [] if row.get("status") == PASS])
    warn_count = len([row for row in checks or [] if row.get("status") == WARN])
    fail_count = len([row for row in checks or [] if row.get("status") == FAIL])
    if fail_count:
        status = BLOCKED
    elif warn_count:
        status = REVIEW
    else:
        status = READY
    return {"subscriber_status": status, "pass_count": pass_count, "warn_count": warn_count, "fail_count": fail_count}


def admin_summary(profiles: Sequence[Mapping[str, Any]], reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    partner_counts = Counter(profile.get("partner") for profile in profiles)
    plan_counts = Counter(profile.get("plan") for profile in profiles)
    risk_counts = Counter(profile.get("risk_level") for profile in profiles)
    return {
        "subscriber_count": len(profiles),
        "enabled_count": sum(1 for profile in profiles if profile.get("enabled")),
        "partner_counts": dict(partner_counts),
        "plan_counts": dict(plan_counts),
        "risk_counts": dict(risk_counts),
        "total_bet_recommendations": sum(int(report.get("bet_count") or 0) for report in reports),
        "total_no_bet_rows": sum(int(report.get("no_bet_count") or 0) for report in reports),
    }


def flatten_reports(reports: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for report in reports or []:
        rows.extend(dict(row) for row in report.get("recommendations") or [])
    return rows


def build_subscriber_intelligence(
    workspace_id: str | None = None,
    subscriber_profiles: Sequence[Mapping[str, Any]] | None = None,
    optimizer_report: Mapping[str, Any] | None = None,
    market_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    profiles = [normalize_profile(profile, index) for index, profile in enumerate(subscriber_profiles or [])]
    markets = market_rows_from_report(optimizer_report, market_rows)
    reports = [personalize_for_subscriber(profile, markets) for profile in profiles if profile.get("enabled")]
    checks = validate_profiles(profiles)
    checks.append(check_row("market_rows_present", "Global market rows supplied", PASS if markets else FAIL, details=f"rows={len(markets)}"))
    checks.append(check_row("shared_engine_separated", "Subscriber profiles separated from shared market rows", PASS if profiles is not markets else FAIL))
    checks.append(check_row("subscriber_specific_reports", "Subscriber-specific reports generated", PASS if reports else FAIL, details=f"reports={len(reports)}"))
    summary = summarize_checks(checks)
    flat = flatten_reports(reports)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "mode": PREVIEW_ONLY,
        **summary,
        "subscriber_count": len(profiles),
        "enabled_subscriber_count": sum(1 for profile in profiles if profile.get("enabled")),
        "market_row_count": len(markets),
        "profiles": profiles,
        "subscriber_reports": reports,
        "personalized_rows": flat,
        "admin_summary": admin_summary(profiles, reports),
        "subscriber_checks": checks,
        "plan_limits": PLAN_LIMITS,
        "safety_gates": {
            "billing_charge_execution": FORBIDDEN,
            "api_key_exposure": FORBIDDEN,
            "live_wager_execution": FORBIDDEN,
            "account_access": FORBIDDEN,
            "funds_movement": FORBIDDEN,
            "automatic_proof_change": FORBIDDEN,
            "automatic_model_change": FORBIDDEN,
            "profit_guarantee": FORBIDDEN,
        },
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": [row for row in checks if row.get("status") == WARN],
        "errors": [row for row in checks if row.get("status") == FAIL],
    }
    report["subscriber_run_id"] = stable_hash("subscriber_run", {"workspace_id": report["workspace_id"], "profiles": profiles, "rows": flat}, 24)
    report["subscriber_hash"] = stable_hash("subscriber_hash", {key: value for key, value in report.items() if key != "generated_at_utc"}, 32)
    return report


def build_subscriber_intelligence_from_text(
    workspace_id: str | None = None,
    profiles_csv_text: str | None = None,
    optimizer_json_text: str | None = None,
    market_csv_text: str | None = None,
) -> dict[str, Any]:
    return build_subscriber_intelligence(workspace_id, parse_csv_text(profiles_csv_text), parse_json_object(optimizer_json_text), parse_csv_text(market_csv_text))


def export_subscriber_intelligence_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_profiles_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("profiles") or [])


def export_personalized_rows_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("personalized_rows") or [])


def export_subscriber_reports_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report.get("subscriber_reports") or []), sort_keys=True, indent=2)


def export_admin_summary_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report.get("admin_summary") or {}), sort_keys=True, indent=2)


def export_subscriber_checks_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("subscriber_checks") or [])


def export_subscriber_manifest_json(report: Mapping[str, Any]) -> str:
    manifest = {key: report.get(key) for key in ("schema_version", "workspace_id", "subscriber_run_id", "subscriber_hash", "generated_at_utc", "subscriber_status", "subscriber_count", "enabled_subscriber_count", "market_row_count", "preview_only", "files_written", "live_changes")}
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
