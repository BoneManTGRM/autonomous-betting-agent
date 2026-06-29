from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.accuracy_calibration_repair_feedback import (
    build_accuracy_calibration_feedback_report,
    model_probability,
)
from autonomous_betting_agent.odds_math_completion import fractional_kelly_stake_fraction
from autonomous_betting_agent.odds_reparodynamics_upgrade_layer import (
    build_phase3e38_upgrade_report,
    expected_value,
    minimum_playable_decimal_odds,
    normalize_decimal_odds,
)
from autonomous_betting_agent.value_math import normalize_probability

SCHEMA_VERSION = "accuracy_decision_integration_preview_v1"
SHADOW_ONLY = "SHADOW ONLY"
PLAYABLE = "PLAYABLE VALUE"
WATCH = "WATCH ONLY"
WAIT = "WAIT FOR BETTER ODDS"
NO_BET = "NO BET"
FORBIDDEN = "FORBIDDEN"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _text(value: Any) -> str:
    return str(value or "").strip()


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


def _id(row: Mapping[str, Any], index: int) -> str:
    for key in ("proof_id", "pick_id", "row_id", "id"):
        if _text(row.get(key)):
            return _text(row.get(key))
    return f"row_{index}"


def _event(row: Mapping[str, Any]) -> str:
    for key in ("event", "event_name", "matchup", "event_id"):
        if _text(row.get(key)):
            return _text(row.get(key))
    return ""


def _selection(row: Mapping[str, Any]) -> str:
    for key in ("selection", "pick", "prediction", "outcome"):
        if _text(row.get(key)):
            return _text(row.get(key))
    return ""


def _sportsbook(row: Mapping[str, Any]) -> str:
    for key in ("sportsbook", "bookmaker", "book"):
        if _text(row.get(key)):
            return _text(row.get(key))
    return ""


def _baseline_decision(probability: float | None, decimal: float | None, *, ev_buffer: float = 0.0, safety_margin: float = 0.02) -> dict[str, Any]:
    ev = expected_value(probability, decimal)
    minimum = minimum_playable_decimal_odds(probability, ev_buffer=ev_buffer, safety_margin=safety_margin)
    blockers: list[str] = []
    if probability is None:
        blockers.append("missing_model_probability")
    if decimal is None:
        blockers.append("missing_decimal_odds")
    if minimum is not None and decimal is not None and decimal < minimum:
        blockers.append("below_minimum_playable_odds")
    if ev is not None and ev <= ev_buffer:
        blockers.append("ev_below_buffer")
    if probability is not None and probability < 0.50:
        blockers.append("probability_below_threshold")
    if blockers:
        action = WAIT if blockers == ["below_minimum_playable_odds"] else NO_BET
    elif ev is not None and ev > ev_buffer:
        action = PLAYABLE
    else:
        action = WATCH
    return {"baseline_EV": ev, "baseline_minimum_playable_odds": minimum, "baseline_action": action, "baseline_blockers": blockers}


def decision_reason(action: str, blockers: Sequence[str], probability_delta: float | None, ev_delta: float | None) -> str:
    if blockers:
        return "; ".join(str(item) for item in blockers)
    if action == PLAYABLE and ev_delta is not None and ev_delta > 0:
        return "calibrated_probability_improved_value"
    if action == PLAYABLE:
        return "calibrated_value_passed_all_gates"
    if probability_delta is not None and probability_delta < 0:
        return "calibration_downgraded_probability"
    return "watch_only_after_calibration"


def simulated_stake_fraction(probability: float | None, decimal: float | None, action: str, *, kelly_fraction: float = 0.25, max_stake_fraction: float = 0.03) -> float:
    if action != PLAYABLE:
        return 0.0
    return fractional_kelly_stake_fraction(probability, decimal, fraction=kelly_fraction, cap=max_stake_fraction)


def old_rank_score(probability: float | None, decimal: float | None) -> float:
    ev = expected_value(probability, decimal)
    return round((probability or 0.0) * 100.0 + (ev or -1.0) * 50.0, 8)


def new_rank_score(probability: float | None, decimal: float | None, action: str, blockers: Sequence[str]) -> float:
    ev = expected_value(probability, decimal)
    score = (probability or 0.0) * 60.0 + (ev or -1.0) * 140.0
    if action == PLAYABLE:
        score += 500.0
    elif action == WATCH:
        score += 100.0
    elif action == WAIT:
        score -= 50.0
    else:
        score -= 200.0
    score -= len(blockers) * 25.0
    return round(score, 8)


def build_decision_preview_rows(
    current_rows: Sequence[Mapping[str, Any]],
    calibration_rows: Sequence[Mapping[str, Any]],
    upgraded_rows: Sequence[Mapping[str, Any]],
    *,
    ev_buffer: float = 0.0,
    safety_margin: float = 0.02,
    kelly_fraction: float = 0.25,
    max_stake_fraction: float = 0.03,
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    calibration_by_index = {int(row.get("row_index", index)): dict(row) for index, row in enumerate(calibration_rows or []) if isinstance(row, Mapping)}
    upgrade_by_index = {int(row.get("row_index", index)): dict(row) for index, row in enumerate(upgraded_rows or []) if isinstance(row, Mapping)}
    for index, row in enumerate(current_rows or []):
        source = dict(row)
        calibration = calibration_by_index.get(index, {})
        upgraded = upgrade_by_index.get(index, {})
        decimal = upgraded.get("best_decimal_odds") or normalize_decimal_odds(source)
        baseline_probability = model_probability(source)
        calibrated_probability = normalize_probability(calibration.get("calibrated_probability"))
        baseline = _baseline_decision(baseline_probability, decimal, ev_buffer=ev_buffer, safety_margin=safety_margin)
        calibrated_ev = expected_value(calibrated_probability, decimal)
        calibrated_minimum = minimum_playable_decimal_odds(calibrated_probability, ev_buffer=ev_buffer, safety_margin=safety_margin)
        blockers: list[str] = []
        if upgraded.get("blockers"):
            blockers.extend(str(item) for item in upgraded.get("blockers") or [])
        if calibration.get("decision_blockers"):
            blockers.extend(str(item) for item in calibration.get("decision_blockers") or [])
        if calibrated_probability is None:
            blockers.append("missing_calibrated_probability")
        if decimal is None:
            blockers.append("missing_decision_odds")
        if calibrated_minimum is not None and decimal is not None and decimal < calibrated_minimum:
            blockers.append("below_calibrated_minimum_playable_odds")
        if calibrated_ev is not None and calibrated_ev <= ev_buffer:
            blockers.append("calibrated_ev_below_buffer")
        if calibrated_probability is not None and calibrated_probability < 0.50:
            blockers.append("calibrated_probability_below_threshold")
        blockers = list(dict.fromkeys(blockers))
        if blockers:
            action = WAIT if blockers == ["below_calibrated_minimum_playable_odds"] else NO_BET
        elif calibrated_ev is not None and calibrated_ev > ev_buffer:
            action = PLAYABLE
        else:
            action = WATCH
        prob_delta = None if calibrated_probability is None or baseline_probability is None else round(calibrated_probability - baseline_probability, 8)
        ev_delta = None if calibrated_ev is None or baseline.get("baseline_EV") is None else round(calibrated_ev - float(baseline["baseline_EV"]), 8)
        stake = simulated_stake_fraction(calibrated_probability, decimal, action, kelly_fraction=kelly_fraction, max_stake_fraction=max_stake_fraction)
        needed = None if calibrated_minimum is None else calibrated_minimum
        output.append({
            "row_index": index,
            "row_id": _id(source, index),
            "event": _event(source),
            "selection": _selection(source),
            "sportsbook": _sportsbook(source),
            "decision_odds": decimal,
            "best_sportsbook": upgraded.get("best_sportsbook") or _sportsbook(source),
            "baseline_probability": baseline_probability,
            "calibrated_probability": calibrated_probability,
            "probability_delta": prob_delta,
            **baseline,
            "calibrated_EV": calibrated_ev,
            "calibrated_minimum_playable_odds": calibrated_minimum,
            "needed_odds_to_play": needed,
            "final_action": action,
            "final_blockers": blockers,
            "decision_reason": decision_reason(action, blockers, prob_delta, ev_delta),
            "calibration_status": calibration.get("calibration_status", ""),
            "price_quality": upgraded.get("price_quality", ""),
            "CLV_status": upgraded.get("CLV_status", ""),
            "simulated_stake_fraction": stake,
            "old_rank_score": old_rank_score(baseline_probability, decimal),
            "new_rank_score": new_rank_score(calibrated_probability, decimal, action, blockers),
            "rank_delta": round(new_rank_score(calibrated_probability, decimal, action, blockers) - old_rank_score(baseline_probability, decimal), 8),
            "shadow_only": True,
        })
    return sorted(output, key=lambda item: item["new_rank_score"], reverse=True)


def summarize_decisions(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    counts = {PLAYABLE: 0, WATCH: 0, WAIT: 0, NO_BET: 0}
    for row in rows or []:
        action = str(row.get("final_action") or NO_BET)
        counts[action] = counts.get(action, 0) + 1
    return {
        "playable_count": counts.get(PLAYABLE, 0),
        "watch_count": counts.get(WATCH, 0),
        "wait_count": counts.get(WAIT, 0),
        "no_bet_count": counts.get(NO_BET, 0),
        "decision_row_count": len(rows or []),
    }


def build_accuracy_decision_integration_report(
    workspace_id: str | None = None,
    current_rows: Sequence[Mapping[str, Any]] | None = None,
    history_rows: Sequence[Mapping[str, Any]] | None = None,
    *,
    min_segment_rows: int = 8,
    shrinkage: float = 20.0,
    ev_buffer: float = 0.0,
    safety_margin: float = 0.02,
    max_age_minutes: int = 180,
    kelly_fraction: float = 0.25,
    max_stake_fraction: float = 0.03,
) -> dict[str, Any]:
    current = [dict(row) for row in current_rows or []]
    history = [dict(row) for row in history_rows or []]
    calibration = build_accuracy_calibration_feedback_report(
        workspace_id,
        current,
        history,
        min_segment_rows=min_segment_rows,
        shrinkage=shrinkage,
        ev_buffer=ev_buffer,
        safety_margin=safety_margin,
    )
    upgrade = build_phase3e38_upgrade_report(
        workspace_id,
        current,
        history,
        ev_buffer=ev_buffer,
        safety_margin=safety_margin,
        max_age_minutes=max_age_minutes,
        min_segment_rows=min_segment_rows,
    )
    decision_rows = build_decision_preview_rows(
        current,
        calibration.get("calibrated_preview_rows") or [],
        upgrade.get("upgraded_odds_rows") or [],
        ev_buffer=ev_buffer,
        safety_margin=safety_margin,
        kelly_fraction=kelly_fraction,
        max_stake_fraction=max_stake_fraction,
    )
    summary = summarize_decisions(decision_rows)
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": _now(),
        "workspace_id": _text(workspace_id) or "default",
        "decision_preview_id": "",
        "mode": SHADOW_ONLY,
        "current_row_count": len(current),
        "history_row_count": len(history),
        **summary,
        "calibration_decision": calibration.get("decision"),
        "calibration_decision_reason": calibration.get("decision_reason"),
        "brier_improvement": calibration.get("brier_improvement"),
        "log_loss_improvement": calibration.get("log_loss_improvement"),
        "repair_feedback_count": calibration.get("repair_feedback_count", 0),
        "upgrade_repair_candidate_count": upgrade.get("repair_candidate_count", 0),
        "decision_preview_rows": decision_rows,
        "calibration_summary": {key: value for key, value in calibration.items() if key not in {"calibration_model", "calibrated_preview_rows", "evaluation_preview_rows", "repair_feedback"}},
        "upgrade_summary": {key: value for key, value in upgrade.items() if key not in {"upgraded_odds_rows", "market_groups", "best_book_rows", "segment_drift", "repair_candidates", "shadow_scoring", "base_odds_report"}},
        "repair_feedback": calibration.get("repair_feedback") or [],
        "safety_gates": {"live_mutation": FORBIDDEN, "model_training": FORBIDDEN, "stored_data_mutation": FORBIDDEN, "automatic_live_promotion": FORBIDDEN, "repairs_applied_live": 0},
        "preview_only": True,
        "files_written": 0,
        "live_changes": 0,
        "warnings": ["decision preview only; manual review required before live use"],
        "errors": [] if current else ["no current rows supplied"],
    }
    report["decision_preview_id"] = stable_hash("accuracy_decision_preview", {"workspace_id": workspace_id, "rows": decision_rows}, 24)
    report["decision_preview_hash"] = stable_hash("accuracy_decision_hash", {k: v for k, v in report.items() if k != "generated_at_utc"}, 32)
    return report


def build_accuracy_decision_integration_report_from_text(
    workspace_id: str | None = None,
    current_csv_text: str | None = None,
    history_csv_text: str | None = None,
    *,
    min_segment_rows: int = 8,
    shrinkage: float = 20.0,
    ev_buffer: float = 0.0,
    safety_margin: float = 0.02,
    max_age_minutes: int = 180,
    kelly_fraction: float = 0.25,
    max_stake_fraction: float = 0.03,
) -> dict[str, Any]:
    return build_accuracy_decision_integration_report(
        workspace_id,
        parse_csv_text(current_csv_text),
        parse_csv_text(history_csv_text),
        min_segment_rows=min_segment_rows,
        shrinkage=shrinkage,
        ev_buffer=ev_buffer,
        safety_margin=safety_margin,
        max_age_minutes=max_age_minutes,
        kelly_fraction=kelly_fraction,
        max_stake_fraction=max_stake_fraction,
    )


def export_accuracy_decision_json(report: Mapping[str, Any]) -> str:
    return json.dumps(_safe(report), sort_keys=True, indent=2)


def export_decision_preview_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("decision_preview_rows") or [])


def export_decision_repair_feedback_csv(report: Mapping[str, Any]) -> str:
    return csv_from_rows(report.get("repair_feedback") or [])
