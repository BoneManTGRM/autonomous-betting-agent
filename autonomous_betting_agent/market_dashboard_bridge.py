from __future__ import annotations

import csv
import hashlib
import io
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.market_optimizer_preview import (
    NO_PLAY,
    PLAYABLE_VALUE,
    PREVIEW_ONLY,
    WAIT_FOR_BETTER_ODDS,
    WATCH_ONLY,
    odds_band,
    safe_float,
)
from autonomous_betting_agent.row_normalizer import safe_text

SCHEMA_VERSION = "market_dashboard_bridge_v1"
TRACKING_SCHEMA_VERSION = "market_tracking_schema_v1"
DASHBOARD_READY = "DASHBOARD READY"
REVIEW_REQUIRED = "REVIEW REQUIRED"
BLOCKED = "BLOCKED"
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
FORBIDDEN = "FORBIDDEN"

TRACKING_FIELDS = (
    "tracking_id",
    "workspace_id",
    "event_id",
    "event",
    "sport",
    "league",
    "sportsbook",
    "market_type",
    "selection",
    "single_vs_chain",
    "pre_game_or_live",
    "favorite_or_underdog",
    "odds_band",
    "confidence_band",
    "risk_level",
    "final_action",
    "decimal_odds",
    "calibrated_probability",
    "calibrated_edge",
    "ev",
    "clv",
    "result",
    "proof_id",
    "chain_id",
    "source_hash",
)


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


def market_rows_from_report(report: Mapping[str, Any] | None, market_rows: Sequence[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    if market_rows:
        return [dict(row) for row in market_rows]
    if not isinstance(report, Mapping):
        return []
    rows = report.get("market_hunter_rows") or report.get("optimizer_rows") or []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def chain_rows_from_report(report: Mapping[str, Any] | None, chain_rows: Sequence[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    if chain_rows:
        return [dict(row) for row in chain_rows]
    if not isinstance(report, Mapping):
        return []
    rows = report.get("chain_builder_rows") or []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def avoid_rows_from_report(report: Mapping[str, Any] | None, avoid_rows: Sequence[Mapping[str, Any]] | None = None) -> list[dict[str, Any]]:
    if avoid_rows:
        return [dict(row) for row in avoid_rows]
    if not isinstance(report, Mapping):
        return []
    rows = report.get("avoid_list") or []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def confidence_band(value: Any) -> str:
    prob = safe_float(value)
    if prob is None:
        return "missing"
    if prob > 1:
        prob = prob / 100.0
    if prob < 0.52:
        return "under_52"
    if prob < 0.58:
        return "52_to_57"
    if prob < 0.65:
        return "58_to_64"
    return "65_plus"


def pre_game_or_live(row: Mapping[str, Any]) -> str:
    text = " ".join(_text(row.get(key)).lower() for key in ("market_phase", "phase", "live", "status", "notes"))
    if "live" in text or "in_play" in text or "in-play" in text:
        return "live"
    return "pre_game"


def favorite_or_underdog(row: Mapping[str, Any]) -> str:
    dec = safe_float(row.get("decimal_odds"))
    if dec is None:
        return "unknown"
    return "favorite" if dec < 2.0 else "underdog"


def value_from_first(row: Mapping[str, Any], keys: Sequence[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if _text(value):
            return value
    return ""


def result_status(row: Mapping[str, Any]) -> str:
    text = _text(row.get("result") or row.get("status") or row.get("outcome") or row.get("grade")).lower()
    if text in {"win", "won", "w"}:
        return "win"
    if text in {"loss", "lost", "l"}:
        return "loss"
    if text in {"push", "void", "cancel", "cancelled", "canceled"}:
        return "push_or_cancel"
    if text in {"pending", "open"}:
        return "pending"
    return text or "unknown"


def build_tracking_row(row: Mapping[str, Any], workspace_id: str, source_type: str = "single") -> dict[str, Any]:
    dec = safe_float(row.get("decimal_odds") or row.get("combined_decimal_odds"))
    prob = safe_float(row.get("calibrated_probability") or row.get("combined_probability"))
    if prob is not None and prob > 1:
        prob = prob / 100.0
    base = {
        "workspace_id": workspace_id,
        "event_id": value_from_first(row, ("event_id", "events")),
        "event": value_from_first(row, ("event", "events")),
        "sport": value_from_first(row, ("sport",)),
        "league": value_from_first(row, ("league",)),
        "sportsbook": value_from_first(row, ("sportsbook", "sportsbooks")),
        "market_type": value_from_first(row, ("market_type", "markets")),
        "selection": value_from_first(row, ("selection", "selections")),
        "single_vs_chain": source_type,
        "pre_game_or_live": pre_game_or_live(row),
        "favorite_or_underdog": favorite_or_underdog(row),
        "odds_band": odds_band(dec),
        "confidence_band": confidence_band(prob),
        "risk_level": value_from_first(row, ("risk_level", "risk_class")),
        "final_action": value_from_first(row, ("final_action",)),
        "decimal_odds": dec,
        "calibrated_probability": prob,
        "calibrated_edge": safe_float(row.get("calibrated_edge")),
        "ev": safe_float(row.get("ev") or row.get("combined_ev")),
        "clv": safe_float(row.get("clv") or row.get("closing_line_value")),
        "result": result_status(row),
        "proof_id": value_from_first(row, ("proof_id",)),
        "chain_id": value_from_first(row, ("chain_id",)),
        "source_hash": stable_hash("source", row, 18),
    }
    base["tracking_id"] = stable_hash("track", base, 18)
    return {field: base.get(field, "") for field in TRACKING_FIELDS}


def build_tracking_rows(workspace_id: str, market_rows: Sequence[Mapping[str, Any]], chain_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows = [build_tracking_row(row, workspace_id, "single") for row in market_rows or []]
    rows.extend(build_tracking_row(row, workspace_id, "chain") for row in chain_rows or [])
    return rows


def validate_tracking_schema(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    fields = set()
    for row in rows or []:
        fields.update(str(key) for key in row.keys())
    for field in TRACKING_FIELDS:
        checks.append(check_row(f"tracking_field_{field}", f"Tracking field present: {field}", PASS if field in fields or not rows else FAIL, actual=field))
    missing_values = []
    for index, row in enumerate(rows or []):
        for field in ("event_id", "sportsbook", "market_type", "selection", "final_action", "odds_band", "confidence_band"):
            if not _text(row.get(field)):
                missing_values.append({"row_index": index, "field": field, "tracking_id": row.get("tracking_id")})
    checks.append(check_row("tracking_required_values", "Required tracking values populated", PASS if not missing_values else WARN, details=f"missing_values={len(missing_values)}"))
    return checks


def check_row(check_id: str, title: str, status: str, details: str = "", expected: Any = "", actual: Any = "") -> dict[str, Any]:
    return {"check_id": check_id, "title": title, "status": status, "details": details, "expected": expected, "actual": actual}


def count_by(rows: Sequence[Mapping[str, Any]], field: str) -> list[dict[str, Any]]:
    counts = Counter(_text(row.get(field)) or "unknown" for row in rows or [])
    return [{field: key, "count": value} for key, value in sorted(counts.items())]


def summarize_market_cards(market_rows: Sequence[Mapping[str, Any]], chain_rows: Sequence[Mapping[str, Any]], avoid_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    action_counts = Counter(_text(row.get("final_action")) for row in market_rows or [])
    risk_counts = Counter(_text(row.get("risk_level")) for row in market_rows or [])
    ev_values = [safe_float(row.get("ev")) for row in market_rows or []]
    ev_clean = [value for value in ev_values if value is not None]
    playable = [dict(row) for row in market_rows or [] if row.get("final_action") == PLAYABLE_VALUE]
    wait = [dict(row) for row in market_rows or [] if row.get("final_action") == WAIT_FOR_BETTER_ODDS]
    watch = [dict(row) for row in market_rows or [] if row.get("final_action") == WATCH_ONLY]
    no_play = [dict(row) for row in market_rows or [] if row.get("final_action") == NO_PLAY]
    chain_preview = [dict(row) for row in chain_rows or [] if _text(row.get("final_action")) == "CHAIN PREVIEW"]
    return {
        "market_rows": len(market_rows or []),
        "playable_count": len(playable),
        "watch_count": len(watch),
        "wait_count": len(wait),
        "no_play_count": len(no_play),
        "chain_preview_count": len(chain_preview),
        "avoid_count": len(avoid_rows or []),
        "low_risk_count": risk_counts.get("LOW", 0),
        "medium_risk_count": risk_counts.get("MEDIUM", 0),
        "high_risk_count": risk_counts.get("HIGH", 0),
        "best_ev": round(max(ev_clean), 6) if ev_clean else None,
        "avg_ev": round(sum(ev_clean) / len(ev_clean), 6) if ev_clean else None,
        "action_counts": dict(action_counts),
        "risk_counts": dict(risk_counts),
        "best_play": playable[0] if playable else None,
    }


def segment_summary(tracking_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in tracking_rows or []:
        key = (_text(row.get("sport")) or "unknown", _text(row.get("league")) or "unknown", _text(row.get("market_type")) or "unknown", _text(row.get("sportsbook")) or "unknown")
        groups[key].append(dict(row))
    output = []
    for (sport, league, market_type, sportsbook), rows in sorted(groups.items()):
        ev_values = [safe_float(row.get("ev")) for row in rows]
        ev_clean = [value for value in ev_values if value is not None]
        actions = Counter(row.get("final_action") for row in rows)
        output.append({
            "sport": sport,
            "league": league,
            "market_type": market_type,
            "sportsbook": sportsbook,
            "row_count": len(rows),
            "playable_count": actions.get(PLAYABLE_VALUE, 0),
            "watch_count": actions.get(WATCH_ONLY, 0),
            "wait_count": actions.get(WAIT_FOR_BETTER_ODDS, 0),
            "no_play_count": actions.get(NO_PLAY, 0),
            "avg_ev": round(sum(ev_clean) / len(ev_clean), 6) if ev_clean else None,
        })
    return output


def proof_handoff_rows(tracking_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for row in tracking_rows or []:
        output.append({
            "tracking_id": row.get("tracking_id"),
            "proof_id": row.get("proof_id"),
            "workspace_id": row.get("workspace_id"),
            "event_id": row.get("event_id"),
            "market_type": row.get("market_type"),
            "sportsbook": row.get("sportsbook"),
            "selection": row.get("selection"),
            "final_action": row.get("final_action"),
            "single_vs_chain": row.get("single_vs_chain"),
            "ev": row.get("ev"),
            "risk_level": row.get("risk_level"),
            "handoff_status": "READY FOR OPERATOR REVIEW",
        })
    return output


def summarize_checks(checks: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pass_count = len([row for row in checks or [] if row.get("status") == PASS])
    warn_count = len([row for row in checks or [] if row.get("status") == WARN])
    fail_count = len([row for row in checks or [] if row.get("status") == FAIL])
    if fail_count:
        status = BLOCKED
    elif warn_count:
        status = REVIEW_REQUIRED
    else:
        status = DASHBOARD_READY
    return {"bridge_status": status, "pass_count": pass_count, "warn_count": warn_count, "fail_count": fail_count}


def build_market_dashboard_bridge(
    workspace_id: str | None = None,
    optimizer_report: Mapping[str, Any] | None = None,
    market_rows: Sequence[Mapping[str, Any]] | None = None,
    chain_rows: Sequence[Mapping[str, Any]] | None = None,
    avoid_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    workspace = _text(workspace_id) or _text((optimizer_report or {}).get("workspace_id")) or "default"
    markets = market_rows_from_report(optimizer_report, market_rows)
    chains = chain_rows_from_report(optimizer_report, chain_rows)
    avoid = avoid_rows_from_report(optimizer_report, avoid_rows)
    tracking = build_tracking_rows(workspace, markets, chains)
    checks = []
    checks.append(check_row("optimizer_rows_present", "Optimizer market rows present", PASS if markets else FAIL, details=f"rows={len(markets)}"))
    checks.append(check_row("optimizer_preview_only", "Optimizer source remains preview-only", PASS if not optimizer_report or optimizer_report.get("preview_only", True) is True else FAIL))
    checks.append(check_row("no_live_changes", "No live changes reported", PASS if not optimizer_report or int(optimizer_report.get("live_changes") or 0) == 0 else FAIL))
    checks.append(check_row("tracking_rows_created", "Tracking rows created", PASS if tracking else FAIL, details=f"rows={len(tracking)}"))
    checks.extend(validate_tracking_schema(tracking))
    cards = summarize_market_cards(markets, chains, avoid)
    segments = segment_summary(tracking)
    handoff = proof_handoff_rows(tracking)
    summary = summarize_checks(checks)
    report = {
        "schema_version": SCHEMA_VERSION,
        "tracking_schema_version": TRACKING_SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": workspace,
        "mode": PREVIEW_ONLY,
        **summary,
        "dashboard_cards": cards,
        "tracking_row_count": len(tracking),
        "market_row_count": len(markets),
        "chain_row_count": len(chains),
        "avoid_row_count": len(avoid),
        "tracking_fields": list(TRACKING_FIELDS),
        "tracking_rows": tracking,
        "segment_summary_rows": segments,
        "action_summary_rows": count_by(tracking, "final_action"),
        "sportsbook_summary_rows": count_by(tracking, "sportsbook"),
        "market_type_summary_rows": count_by(tracking, "market_type"),
        "proof_handoff_rows": handoff,
        "avoid_summary_rows": avoid,
        "bridge_checks": checks,
        "safety_gates": {
            "live_execution": FORBIDDEN,
            "account_access": FORBIDDEN,
            "funds_movement": FORBIDDEN,
            "automatic_proof_change": FORBIDDEN,
            "automatic_model_change": FORBIDDEN,
            "key_exposure": FORBIDDEN,
            "profit_guarantee": FORBIDDEN,
        },
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": [row for row in checks if row.get("status") == WARN],
        "errors": [row for row in checks if row.get("status") == FAIL],
    }
    report["bridge_id"] = stable_hash("market_bridge", {"workspace_id": workspace, "tracking": tracking, "checks": checks}, 24)
    report["bridge_hash"] = stable_hash("market_bridge_hash", {key: value for key, value in report.items() if key != "generated_at_utc"}, 32)
    return report


def build_market_dashboard_bridge_from_text(
    workspace_id: str | None = None,
    optimizer_json_text: str | None = None,
    market_csv_text: str | None = None,
    chain_csv_text: str | None = None,
    avoid_csv_text: str | None = None,
) -> dict[str, Any]:
    return build_market_dashboard_bridge(
        workspace_id,
        parse_json_object(optimizer_json_text),
        parse_csv_text(market_csv_text),
        parse_csv_text(chain_csv_text),
        parse_csv_text(avoid_csv_text),
    )


def export_market_bridge_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_tracking_schema_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("tracking_rows") or [])


def export_segment_summary_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("segment_summary_rows") or [])


def export_proof_handoff_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("proof_handoff_rows") or [])


def export_dashboard_cards_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report.get("dashboard_cards") or {}), sort_keys=True, indent=2)


def export_market_bridge_checks_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("bridge_checks") or [])


def export_market_bridge_manifest_json(report: Mapping[str, Any]) -> str:
    manifest = {key: report.get(key) for key in ("schema_version", "tracking_schema_version", "workspace_id", "bridge_id", "bridge_hash", "generated_at_utc", "bridge_status", "tracking_row_count", "market_row_count", "chain_row_count", "avoid_row_count", "preview_only", "files_written", "live_changes")}
    return json.dumps(_safe(manifest), sort_keys=True, indent=2)
