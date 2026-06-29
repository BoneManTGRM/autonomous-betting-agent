from __future__ import annotations

from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping, Sequence

import pandas as pd

REVIEW_ELIGIBLE = "REVIEW_ELIGIBLE"
REVIEW_BLOCKED = "REVIEW_BLOCKED"
REVIEW_WATCHLIST_ONLY = "REVIEW_WATCHLIST_ONLY"
REVIEW_PREDICTION_ONLY = "REVIEW_PREDICTION_ONLY"
REVIEW_ALREADY_REVIEWED = "REVIEW_ALREADY_REVIEWED"
REVIEW_UNKNOWN = "REVIEW_UNKNOWN"

NOT_SELECTED = "NOT_SELECTED"
MANUAL_CANDIDATE_ONLY = "MANUAL_CANDIDATE_ONLY"
MANUAL_CANDIDATE_BLOCKED = "MANUAL_CANDIDATE_BLOCKED"
MANUAL_CANDIDATE_REVIEW_REQUIRED = "MANUAL_CANDIDATE_REVIEW_REQUIRED"

PLAYABLE_PLUS_EV = "PLAYABLE_PLUS_EV"
WATCHLIST_VALUE = "WATCHLIST_VALUE"
PREDICTION_ONLY_NOT_PLUS_EV = "PREDICTION_ONLY_NOT_PLUS_EV"
COMPLETE_MARKET = "COMPLETE_MARKET"
EXPLAINED_PLAYABLE_PLUS_EV = "EXPLAINED_PLAYABLE_PLUS_EV"

BLOCKING_EXPLANATIONS = {
    "EXPLAINED_SOURCE_BLOCKED",
    "EXPLAINED_MARKET_INCOMPLETE",
    "EXPLAINED_NO_VIG_UNAVAILABLE",
    "EXPLAINED_STALE_OR_HISTORICAL",
    "EXPLAINED_BLOCKED",
    "EXPLAINED_UNKNOWN",
}

REVIEW_COLUMNS = [
    "advisory_manual_review_eligible",
    "advisory_manual_review_status",
    "advisory_manual_review_reason",
    "advisory_manual_review_blockers",
    "advisory_manual_review_warnings",
    "advisory_manual_review_next_action",
    "advisory_candidate_review_status",
    "advisory_candidate_review_created_at",
    "advisory_candidate_review_source",
    "advisory_candidate_review_safety_notes",
    "advisory_candidate_review_row_id",
]


def _records(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame | None) -> list[dict[str, Any]]:
    if rows_or_frame is None:
        return []
    if isinstance(rows_or_frame, pd.DataFrame):
        return rows_or_frame.to_dict("records")
    return [deepcopy(dict(row)) for row in rows_or_frame if isinstance(row, Mapping)]


def _text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"none", "nan", "null", "nat"} else text


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _text(value).lower() in {"true", "1", "yes", "y", "available"}


def _csv(values: Sequence[str]) -> str:
    return ",".join(dict.fromkeys([value for value in values if value]))


def _pipe(values: Sequence[str]) -> str:
    return " | ".join(dict.fromkeys([value for value in values if value]))


def _status(row: Mapping[str, Any]) -> str:
    return _text(row.get("advisory_calibrated_playable_status")) or _text(row.get("advisory_playable_status"))


def _base_status(row: Mapping[str, Any]) -> str:
    return _text(row.get("advisory_playable_status")) or _text(row.get("advisory_calibrated_playable_status"))


def candidate_row_id(row: Mapping[str, Any]) -> str:
    existing = _text(row.get("advisory_candidate_review_row_id"))
    if existing:
        return existing
    parts = {
        "event": _text(row.get("event") or row.get("event_name") or row.get("matchup") or row.get("game")),
        "prediction": _text(row.get("prediction") or row.get("selection") or row.get("pick")),
        "market": _text(row.get("market_type") or row.get("market") or row.get("bet_type")),
        "book": _text(row.get("sportsbook") or row.get("bookmaker") or row.get("book")),
        "status": _status(row),
        "price": _text(row.get("advisory_current_decimal_odds") or row.get("decimal_odds") or row.get("odds")),
    }
    encoded = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:16]


def _hard_blockers(row: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    explanation = _text(row.get("advisory_explanation_status"))
    source = _text(row.get("advisory_sportsbook_source_type"))
    market = _text(row.get("advisory_market_completeness_status"))
    stale = _text(row.get("advisory_stale_line_status"))
    reason = _text(row.get("advisory_playable_reason"))
    status = _status(row)

    required = ["advisory_playable_status", "advisory_explanation_status", "advisory_sportsbook_source_type", "advisory_market_completeness_status"]
    missing = [field for field in required if field not in row]
    if missing:
        blockers.append("missing_required_advisory_fields:" + ",".join(missing))
    if stale in {"STALE", "EVENT_STARTED", "HISTORICAL_ROW"} or reason == "event_start_time_is_not_future":
        blockers.append("stale_or_historical")
    if source == "CONSENSUS_ONLY" or _truthy(row.get("advisory_is_consensus_source")):
        blockers.append("consensus_only_source")
    if source == "UNKNOWN_SOURCE":
        blockers.append("unknown_sportsbook_source")
    if market and market != COMPLETE_MARKET:
        blockers.append("incomplete_market")
    if "advisory_no_vig_available" in row and not _truthy(row.get("advisory_no_vig_available")):
        blockers.append("no_vig_unavailable")
    if status.startswith("BLOCKED") or _base_status(row).startswith("BLOCKED"):
        blockers.append("hard_blocked_advisory_status")
    if explanation in BLOCKING_EXPLANATIONS:
        blockers.append("blocking_explanation_status:" + explanation)
    return blockers


def candidate_review_diagnostics(row: Mapping[str, Any]) -> dict[str, Any]:
    status = _status(row)
    base_status = _base_status(row)
    explanation = _text(row.get("advisory_explanation_status"))
    source = _text(row.get("advisory_sportsbook_source_type"))
    blockers = _hard_blockers(row)
    warnings: list[str] = []
    if _text(row.get("advisory_shadow_readiness_status")) and _text(row.get("advisory_shadow_readiness_status")) != "SHADOW_READY":
        warnings.append("shadow_model_context_only:" + _text(row.get("advisory_shadow_readiness_status")))
    real_source = source == "REAL_SPORTSBOOK" or _truthy(row.get("advisory_is_real_sportsbook"))
    market_complete = _text(row.get("advisory_market_completeness_status")) == COMPLETE_MARKET
    no_vig = _truthy(row.get("advisory_no_vig_available"))
    is_playable = status == PLAYABLE_PLUS_EV or base_status == PLAYABLE_PLUS_EV

    if blockers:
        review_status = REVIEW_BLOCKED
        reason = "Row has hard review blockers."
        eligible = False
        next_action = "Resolve the blockers before local candidate review."
    elif base_status == WATCHLIST_VALUE or status == WATCHLIST_VALUE:
        review_status = REVIEW_WATCHLIST_ONLY
        reason = "Watchlist rows are context only and cannot become candidates."
        eligible = False
        next_action = "Keep this row on watchlist until it becomes explained playable +EV."
    elif base_status == PREDICTION_ONLY_NOT_PLUS_EV or status == PREDICTION_ONLY_NOT_PLUS_EV:
        review_status = REVIEW_PREDICTION_ONLY
        reason = "Prediction-only rows are not value candidates."
        eligible = False
        next_action = "Treat as prediction-only unless price/value improves."
    elif is_playable and explanation == EXPLAINED_PLAYABLE_PLUS_EV and real_source and market_complete and no_vig:
        review_status = REVIEW_ELIGIBLE
        reason = "Row passes local candidate review gates."
        eligible = True
        next_action = "Eligible for manual local review selection."
    elif is_playable:
        review_status = REVIEW_BLOCKED
        reason = "Playable status is present, but required explanation/source/market/no-vig gates are incomplete."
        eligible = False
        next_action = "Run advisory explanation/source/market checks before selecting."
    else:
        review_status = REVIEW_UNKNOWN
        reason = "Candidate review state is unknown."
        eligible = False
        next_action = "Run the advisory value and explanation pipeline."

    existing_status = _text(row.get("advisory_candidate_review_status")) or NOT_SELECTED
    existing_created_at = _text(row.get("advisory_candidate_review_created_at"))
    return {
        "advisory_manual_review_eligible": eligible,
        "advisory_manual_review_status": review_status,
        "advisory_manual_review_reason": reason,
        "advisory_manual_review_blockers": _csv(blockers),
        "advisory_manual_review_warnings": _pipe(warnings),
        "advisory_manual_review_next_action": next_action,
        "advisory_candidate_review_status": existing_status,
        "advisory_candidate_review_created_at": existing_created_at,
        "advisory_candidate_review_source": "phase_3e6_manual_candidate_review_gate",
        "advisory_candidate_review_safety_notes": "Local review candidate only; no official lock, no proof publish, no ledger write, no stake or bankroll action.",
        "advisory_candidate_review_row_id": candidate_row_id(row),
    }


def candidate_review_rows(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in _records(rows_or_frame):
        item = deepcopy(row)
        item.update(candidate_review_diagnostics(item))
        out.append(item)
    return out


def apply_manual_candidate_selection(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame, selected_row_ids: Sequence[str] | None = None) -> list[dict[str, Any]]:
    selected = set(selected_row_ids or [])
    stamped = datetime.now(timezone.utc).isoformat() if selected else ""
    rows = candidate_review_rows(rows_or_frame)
    out: list[dict[str, Any]] = []
    for row in rows:
        item = deepcopy(row)
        row_id = _text(item.get("advisory_candidate_review_row_id"))
        if row_id in selected:
            if item.get("advisory_manual_review_eligible") is True:
                item["advisory_candidate_review_status"] = MANUAL_CANDIDATE_ONLY
                item["advisory_candidate_review_created_at"] = stamped
            else:
                item["advisory_candidate_review_status"] = MANUAL_CANDIDATE_BLOCKED
                item["advisory_candidate_review_created_at"] = stamped
        out.append(item)
    return out


def candidate_review_summary(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    rows = candidate_review_rows(rows_or_frame)
    if not rows:
        return pd.DataFrame(columns=["advisory_manual_review_status", "advisory_candidate_review_status", "row_count"])
    frame = pd.DataFrame(rows)
    return frame.groupby(["advisory_manual_review_status", "advisory_candidate_review_status"], dropna=False).size().reset_index(name="row_count").sort_values("row_count", ascending=False, ignore_index=True)


def candidate_review_blocker_summary(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> pd.DataFrame:
    counter: Counter[str] = Counter()
    for row in candidate_review_rows(rows_or_frame):
        for blocker in _text(row.get("advisory_manual_review_blockers")).split(","):
            if blocker:
                counter[blocker] += 1
    return pd.DataFrame([{"candidate_blocker": blocker, "row_count": count} for blocker, count in counter.most_common()])


def candidate_review_report_section(rows_or_frame: Sequence[Mapping[str, Any]] | pd.DataFrame) -> str:
    rows = candidate_review_rows(rows_or_frame)
    frame = pd.DataFrame(rows)
    if frame.empty:
        return "Manual Advisory Candidate Review Gate\n- No candidate review rows available."
    eligible = int((frame["advisory_manual_review_status"] == REVIEW_ELIGIBLE).sum())
    selected = int((frame["advisory_candidate_review_status"] == MANUAL_CANDIDATE_ONLY).sum())
    blocked = int((frame["advisory_manual_review_status"] == REVIEW_BLOCKED).sum())
    blockers = candidate_review_blocker_summary(frame).head(5).to_dict("records")
    lines = [
        "Manual Advisory Candidate Review Gate",
        f"- Eligible local review candidates: {eligible}",
        f"- Selected manual candidates: {selected}",
        f"- Blocked candidate rows: {blocked}",
        "- Safety: local/session/export only; no official lock, no proof publish, no ledger write, no stake or bankroll action.",
    ]
    if blockers:
        lines.append("- Top candidate blockers:")
        for item in blockers:
            lines.append(f"  - {item.get('candidate_blocker')}: {item.get('row_count')}")
    return "\n".join(lines)
