from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.event_match_resolver import parse_csv_text

SCHEMA_VERSION = "adaptive_learning_intake_v1"
VERIFIED = "VERIFIED LANE"
REVIEW = "REVIEW LANE"
SHADOW = "SHADOW LANE"
QUARANTINE = "QUARANTINE LANE"
LANES = (VERIFIED, REVIEW, SHADOW, QUARANTINE)
INTAKE_READY = "INTAKE READY"
INTAKE_REVIEW = "REVIEW REQUIRED"
INTAKE_EMPTY = "NO ROWS"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _text(value).lower()


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


def parse_json_object(text: str | None) -> dict[str, Any]:
    raw = _text(text)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {"parse_error": "invalid_json"}
    return dict(parsed) if isinstance(parsed, Mapping) else {"value": parsed}


def parse_json_rows(text: str | None) -> list[dict[str, Any]]:
    raw = _text(text)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except Exception:
        return [{"parse_error": "invalid_json"}]
    if isinstance(parsed, list):
        return [dict(item) if isinstance(item, Mapping) else {"value": item} for item in parsed]
    if isinstance(parsed, Mapping):
        for key in ("rows", "items", "data", "review_rows", "shadow_rows", "learning_rows"):
            value = parsed.get(key)
            if isinstance(value, list):
                return [dict(item) if isinstance(item, Mapping) else {"value": item} for item in value]
        return [dict(parsed)]
    return [{"value": parsed}]


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


def _float(value: Any) -> float | None:
    text = _text(value).replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _row_event(row: Mapping[str, Any]) -> str:
    for key in ("event", "event_name", "matchup", "locked_event", "matched_provider_event"):
        if _text(row.get(key)):
            return _text(row.get(key))
    return ""


def _row_id(row: Mapping[str, Any], index: int = 0) -> str:
    for key in ("locked_row_id", "proof_id", "row_id", "id", "event_id"):
        if _text(row.get(key)):
            return _text(row.get(key))
    return f"row_{index}"


def _confidence(row: Mapping[str, Any]) -> float:
    for key in ("match_confidence", "best_score", "confidence", "source_confidence"):
        value = _float(row.get(key))
        if value is not None:
            return value / 100.0 if value > 1 else value
    return 0.0


def _has_confirmation(row: Mapping[str, Any]) -> bool:
    return bool(_text(row.get("confirmation_value") or row.get("final_score") or row.get("result") or row.get("grade")))


def _has_usable_context(row: Mapping[str, Any]) -> bool:
    return bool(_row_event(row) or _text(row.get("selection") or row.get("pick") or row.get("market_type") or row.get("latest_value")))


def _malformed_reasons(row: Mapping[str, Any]) -> list[str]:
    reasons: list[str] = []
    if row.get("parse_error") == "invalid_json":
        reasons.append("invalid json")
    confidence = _confidence(row)
    if confidence < 0 or confidence > 1:
        reasons.append("confidence outside valid range")
    if not _has_usable_context(row):
        reasons.append("missing event or usable context")
    for key in ("decimal_odds", "odds", "latest_value", "original_value"):
        value = _float(row.get(key))
        if value is not None and value < 0:
            reasons.append(f"negative numeric field: {key}")
    return reasons


def route_learning_row(
    row: Mapping[str, Any],
    *,
    source: str = "manual",
    row_index: int = 0,
    verified_confidence: float = 0.82,
    review_confidence: float = 0.50,
) -> dict[str, Any]:
    item = dict(row or {})
    reasons = _malformed_reasons(item)
    confidence = _confidence(item)
    status_text = _lower(item.get("status") or item.get("verification_status") or item.get("learning_status"))
    manual_flag = bool(item.get("manual_review_required")) or "manual" in status_text or "review" in status_text
    if reasons:
        lane = QUARANTINE
    elif manual_flag or status_text in {"low confidence", "no match", "duplicate match"}:
        lane = REVIEW
        reasons.append("human review required")
    elif status_text in {"verified_ready", "ready_for_manual_import", "matched"} and _has_confirmation(item) and confidence >= verified_confidence:
        lane = VERIFIED
        reasons.append("verified row with confirmation and sufficient confidence")
    elif confidence >= review_confidence and _has_usable_context(item):
        lane = REVIEW
        reasons.append("usable row below verified threshold")
    else:
        lane = SHADOW
        reasons.append("shadow observation only")
    return {
        "intake_row_id": _row_id(item, row_index),
        "source": source,
        "lane": lane,
        "event": _row_event(item),
        "selection": item.get("selection") or item.get("pick") or item.get("prediction") or "",
        "confidence": round(confidence, 6),
        "confirmation_value": item.get("confirmation_value") or item.get("final_score") or item.get("result") or "",
        "latest_value": item.get("latest_value") or item.get("closing_value") or "",
        "value_delta_percent": item.get("value_delta_percent") or item.get("clv_percent") or "",
        "official_metrics_allowed": lane == VERIFIED,
        "shadow_learning_allowed": lane in {VERIFIED, REVIEW, SHADOW},
        "requires_review": lane == REVIEW,
        "quarantined": lane == QUARANTINE,
        "reasons": reasons,
        "raw_row": item,
    }


def extract_package_rows(package: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key, source in (
        ("verified_learning_rows", "package_verified"),
        ("manual_review_rows", "package_review"),
        ("diff_rows", "package_diff"),
    ):
        value = package.get(key) if isinstance(package, Mapping) else []
        for item in value or []:
            if isinstance(item, Mapping):
                row = dict(item)
                row["_intake_source"] = source
                rows.append(row)
    return rows


def build_adaptive_learning_intake(
    workspace_id: str | None = None,
    package: Mapping[str, Any] | None = None,
    shadow_rows: Sequence[Mapping[str, Any]] | None = None,
    review_rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    verified_confidence: float = 0.82,
    review_confidence: float = 0.50,
) -> dict[str, Any]:
    package_rows = extract_package_rows(dict(package or {}))
    extras = [dict(row) for row in shadow_rows or []]
    reviews = [dict(row) for row in review_rows or []]
    all_rows: list[tuple[str, dict[str, Any]]] = []
    for row in package_rows:
        all_rows.append((_text(row.pop("_intake_source", "package")), row))
    for row in extras:
        all_rows.append(("shadow_extra", row))
    for row in reviews:
        row.setdefault("manual_review_required", True)
        all_rows.append(("review_extra", row))
    routed = [route_learning_row(row, source=source, row_index=index, verified_confidence=verified_confidence, review_confidence=review_confidence) for index, (source, row) in enumerate(all_rows)]
    by_lane = {lane: [row for row in routed if row["lane"] == lane] for lane in LANES}
    total = len(routed)
    status = INTAKE_EMPTY if total == 0 else INTAKE_REVIEW if by_lane[REVIEW] or by_lane[QUARANTINE] else INTAKE_READY
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "intake_id": "",
        "status": status,
        "total_rows": total,
        "verified_count": len(by_lane[VERIFIED]),
        "review_count": len(by_lane[REVIEW]),
        "shadow_count": len(by_lane[SHADOW]),
        "quarantine_count": len(by_lane[QUARANTINE]),
        "official_metrics_row_count": len(by_lane[VERIFIED]),
        "shadow_learning_row_count": len(by_lane[VERIFIED]) + len(by_lane[REVIEW]) + len(by_lane[SHADOW]),
        "verified_confidence": float(verified_confidence),
        "review_confidence": float(review_confidence),
        "preview_only": True,
        "files_written": 0,
        "lane_rows": by_lane,
        "warnings": ["review lane has rows"] if by_lane[REVIEW] else [],
        "errors": ["quarantine lane has rows"] if by_lane[QUARANTINE] else [],
    }
    report["intake_id"] = stable_hash("adaptive_intake", {"workspace_id": workspace_id, "lane_rows": by_lane}, 24)
    report["intake_hash"] = stable_hash("adaptive_intake_hash", {k: v for k, v in report.items() if k != "generated_at_utc"}, 32)
    return report


def build_adaptive_learning_intake_from_text(
    workspace_id: str | None = None,
    package_json_text: str | None = None,
    shadow_csv_text: str | None = None,
    review_json_text: str | None = None,
    *,
    verified_confidence: float = 0.82,
    review_confidence: float = 0.50,
) -> dict[str, Any]:
    return build_adaptive_learning_intake(
        workspace_id,
        parse_json_object(package_json_text),
        parse_csv_text(shadow_csv_text),
        parse_json_rows(review_json_text),
        verified_confidence=verified_confidence,
        review_confidence=review_confidence,
    )


def lane_csv(report: Mapping[str, Any], lane: str) -> str:
    rows = []
    for row in ((report.get("lane_rows") or {}).get(lane) or []):
        if isinstance(row, Mapping):
            rows.append({key: value for key, value in row.items() if key != "raw_row"})
    return csv_from_rows(rows)


def export_intake_manifest_json(report: Mapping[str, Any]) -> str:
    compact = dict(report or {})
    compact["lane_rows"] = {lane: [{key: value for key, value in row.items() if key != "raw_row"} for row in rows] for lane, rows in dict(compact.get("lane_rows") or {}).items()}
    return json.dumps(_safe(compact), sort_keys=True, indent=2)
