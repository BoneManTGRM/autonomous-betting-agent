from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.dynamic_odds_predictor import dynamic_value_metrics, learn_lr_multipliers
from autonomous_betting_agent.dynamic_odds_shadow_memory import (
    GLOBAL_BASELINE,
    BASELINE_FLOOR,
    completed_win_loss_rows,
    feature_influence_rows,
    infer_workspace_id,
    load_dynamic_odds_shadow_model,
    protected_baseline_metrics,
    runtime_lr_model,
    shadow_model_status,
    training_result_stats,
)

SHADOW_ONLY = "SHADOW ONLY"

DISPLAY_COLUMNS = [
    "event",
    "prediction",
    "market_type",
    "sportsbook",
    "decimal_odds",
    "current_model_probability",
    "raw_implied_probability",
    "no_vig_implied_probability",
    "book_odds_ratio",
    "total_LR_multiplier",
    "recency_decay_factor",
    "dynamic_probability",
    "probability_delta",
    "dynamic_edge",
    "current_edge",
    "dynamic_edge_delta",
    "dynamic_no_vig_edge",
    "dynamic_EV",
    "current_EV",
    "dynamic_EV_delta",
    "dynamic_fair_odds",
    "global_baseline",
    "segment_baseline",
    "protected_baseline",
    "baseline_floor",
    "baseline_floor_active",
    "baseline_source",
    "baseline_confidence",
    "baseline_prior_weight",
    "segment_sample_size",
    "segment_underperforming",
    "segment_outperforming",
    "dynamic_above_protected_baseline",
    "dynamic_below_protected_baseline",
    "baseline_regression_blocked",
    "baseline_protection_reason",
    "shadow_decision_label",
    "strongest_LR_feature",
    "strongest_LR_multiplier",
    "strongest_LR_reason",
    "LR_feature_count",
    "missing_LR_feature_count",
    "baseline_vs_dynamic_status",
    "dynamic_signal_status",
    "dynamic_odds_mode",
    "lr_model_loaded",
    "lr_model_source",
    "lr_model_last_trained_at_utc",
    "model_quality_label",
    "model_quality_reason",
    "baseline_protection_active",
    "completed_rows_seen",
    "wins",
    "losses",
    "pushes_excluded",
    "lr_training_rows_used",
    "lr_feature_count",
    "strong_feature_count",
    "weak_feature_count",
    "insufficient_feature_count",
    "dynamic_odds_applied_live_count",
]

RESULT_KEYS = (
    "result",
    "grade",
    "outcome",
    "official_result",
    "final_result",
    "result_status",
    "pick_result",
    "settled_status",
)
COMPLETED_TOKENS = {
    "win",
    "won",
    "w",
    "loss",
    "lost",
    "l",
}


def _first_text(row: Mapping[str, Any], names: Sequence[str]) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() and str(value).strip().lower() not in {"nan", "none"}:
            return str(value).strip()
    return ""


def _round(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def _is_completed_row(row: Mapping[str, Any]) -> bool:
    text = " ".join(str(row.get(key, "") or "").strip().lower() for key in RESULT_KEYS)
    return any(token in text.split() or token in text for token in COMPLETED_TOKENS)


def _has_learned_lr(metrics: Mapping[str, Any], lr_model: Mapping[str, Any] | None) -> bool:
    model = dict(lr_model or {})
    if int(model.get("feature_count") or 0) > 0:
        return True
    for item in metrics.get("LR_breakdown", []) or []:
        if isinstance(item, Mapping) and int(item.get("sample_size") or 0) > 0 and str(item.get("reason") or "") != "no_lr_data_default_lr":
            return True
    return False


def _lr_model_from_rows(rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    completed = completed_win_loss_rows(rows)
    stats = training_result_stats(rows)
    model = learn_lr_multipliers(completed, config) if completed else learn_lr_multipliers([], config)
    baseline = protected_baseline_metrics(stats["wins"], stats["losses"], config)
    model.update({**stats, **baseline})
    model["model_source"] = "current_completed_rows_shadow_learning_unsaved" if completed else "no_lr_data"
    model["last_trained_at_utc"] = ""
    model["dynamic_odds_applied_live_count"] = 0
    model.setdefault("model_quality_label", baseline.get("baseline_confidence", "DATA BLOCKED"))
    model.setdefault("model_quality_reason", "current_rows_only_unsaved")
    return model


def _resolve_lr_model(rows: Sequence[Mapping[str, Any]] | None, lr_model: Mapping[str, Any] | None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Resolve Shadow LR math without mutating disk or official pick fields.

    Phase 3E.4 requires Streamlit rerenders to be idempotent. A saved Shadow
    model may be loaded and used for pending rows, but unsaved completed rows
    are evaluated in memory only. Persistent training is reserved for the
    explicit trainer button in the shared control panel.
    """

    source_rows = [deepcopy(dict(row)) for row in list(rows or []) if isinstance(row, Mapping)]
    model = deepcopy(dict(lr_model or {}))
    if model:
        model.setdefault("model_source", "provided_shadow_model")
        model.setdefault("last_trained_at_utc", "")
        model["dynamic_odds_applied_live_count"] = 0
        return model
    workspace_id = infer_workspace_id(source_rows)
    saved_payload = load_dynamic_odds_shadow_model(workspace_id)
    if int((saved_payload.get("lr_model") or {}).get("feature_count") or saved_payload.get("feature_count") or 0) > 0:
        return runtime_lr_model(saved_payload)
    return _lr_model_from_rows(source_rows, config)


def _strongest_lr(metrics: Mapping[str, Any]) -> dict[str, Any]:
    items = [dict(item) for item in metrics.get("LR_breakdown", []) or [] if isinstance(item, Mapping)]
    if not items:
        return {"feature": "", "multiplier": None, "reason": "no_lr_data", "missing_count": 0, "count": 0}
    strongest = max(items, key=lambda item: abs(float(item.get("capped_lr") or 1.0) - 1.0))
    missing = sum(1 for item in items if int(item.get("sample_size") or 0) <= 0 or str(item.get("reason") or "") == "no_lr_data_default_lr")
    feature = f"{strongest.get('feature_group', '')}|{strongest.get('feature_value', '')}".strip("|")
    return {
        "feature": feature,
        "multiplier": strongest.get("capped_lr"),
        "reason": strongest.get("reason") or "",
        "missing_count": missing,
        "count": len(items),
    }


def _shadow_decision(status: str, probability_delta: float | None, ev_delta: float | None, below_protected: bool, model_quality: str) -> str:
    weak = model_quality in {"DATA BLOCKED", "WEAK SAMPLE", "USABLE SAMPLE", "NEEDS MORE DATA"}
    if status in {"no_odds", "no_lr_data"}:
        return "shadow_needs_more_data"
    if below_protected:
        return "shadow_blocked_by_baseline_guard"
    if weak and ((probability_delta is not None and probability_delta < 0) or (ev_delta is not None and ev_delta < 0)):
        return "shadow_neutral"
    if (probability_delta is not None and probability_delta > 0) or (ev_delta is not None and ev_delta > 0):
        return "shadow_improved"
    if (probability_delta is not None and probability_delta < 0) or (ev_delta is not None and ev_delta < 0):
        return "shadow_regressed"
    return "shadow_neutral"


def build_dynamic_odds_shadow_row(row: Mapping[str, Any], lr_model: Mapping[str, Any] | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build one display-only Dynamic Odds row without mutating the source row."""

    source = deepcopy(dict(row or {}))
    model = deepcopy(dict(lr_model or {}))
    metrics = dynamic_value_metrics(source, lr_model=model, config=config)
    status = metrics.get("dynamic_signal_status") or "shadow_only"
    if metrics.get("decimal_odds") is None:
        status = "no_odds"
    elif not _has_learned_lr(metrics, model):
        status = "no_lr_data"
    strongest = _strongest_lr(metrics)
    probability_delta = None
    if metrics.get("dynamic_probability") is not None and metrics.get("current_model_probability") is not None:
        probability_delta = float(metrics["dynamic_probability"]) - float(metrics["current_model_probability"])
    dynamic_edge_delta = None
    if metrics.get("dynamic_edge") is not None and metrics.get("current_edge") is not None:
        dynamic_edge_delta = float(metrics["dynamic_edge"]) - float(metrics["current_edge"])
    dynamic_ev_delta = None
    if metrics.get("dynamic_EV") is not None and metrics.get("current_EV") is not None:
        dynamic_ev_delta = float(metrics["dynamic_EV"]) - float(metrics["current_EV"])
    current_status = str(metrics.get("current_value_color") or "baseline_unknown")
    model_loaded = int(model.get("feature_count") or 0) > 0
    protected = model.get("protected_baseline")
    dynamic_probability = metrics.get("dynamic_probability")
    above_protected = bool(dynamic_probability is not None and protected is not None and float(dynamic_probability) >= float(protected))
    below_protected = bool(dynamic_probability is not None and protected is not None and float(dynamic_probability) < float(protected))
    quality = str(model.get("model_quality_label") or model.get("baseline_confidence") or "DATA BLOCKED")
    regression_blocked = bool(below_protected)
    protection_reason = "dynamic_probability_below_protected_baseline" if regression_blocked else "not_blocked"
    decision = _shadow_decision(status, probability_delta, dynamic_ev_delta, below_protected, quality)
    return {
        "event": _first_text(source, ["event", "event_name", "matchup", "game"]),
        "prediction": _first_text(source, ["prediction", "pick", "selection", "public_pick"]),
        "market_type": _first_text(source, ["market_type", "market", "bet_type"]),
        "sportsbook": _first_text(source, ["sportsbook", "bookmaker", "book", "odds_source"]),
        "decimal_odds": metrics.get("decimal_odds"),
        "current_model_probability": metrics.get("current_model_probability"),
        "raw_implied_probability": metrics.get("raw_implied_probability"),
        "no_vig_implied_probability": metrics.get("no_vig_implied_probability"),
        "book_odds_ratio": metrics.get("book_odds_ratio"),
        "total_LR_multiplier": metrics.get("total_LR_multiplier", 1.0),
        "recency_decay_factor": metrics.get("recency_decay_factor", 1.0),
        "dynamic_probability": dynamic_probability,
        "probability_delta": _round(probability_delta),
        "dynamic_edge": metrics.get("dynamic_edge"),
        "current_edge": metrics.get("current_edge"),
        "dynamic_edge_delta": _round(dynamic_edge_delta),
        "dynamic_no_vig_edge": metrics.get("dynamic_no_vig_edge"),
        "dynamic_EV": metrics.get("dynamic_EV"),
        "current_EV": metrics.get("current_EV"),
        "dynamic_EV_delta": _round(dynamic_ev_delta),
        "dynamic_fair_odds": metrics.get("dynamic_fair_odds"),
        "global_baseline": model.get("global_baseline", GLOBAL_BASELINE),
        "segment_baseline": model.get("segment_baseline"),
        "protected_baseline": model.get("protected_baseline", BASELINE_FLOOR),
        "baseline_floor": model.get("baseline_floor", BASELINE_FLOOR),
        "baseline_floor_active": bool(model.get("baseline_floor_active", False)),
        "baseline_source": model.get("baseline_source", "user_global_baseline_prior_no_data"),
        "baseline_confidence": model.get("baseline_confidence", "DATA BLOCKED"),
        "baseline_prior_weight": int(model.get("baseline_prior_weight") or 150),
        "segment_sample_size": int(model.get("segment_sample_size") or model.get("completed_rows_seen") or 0),
        "segment_underperforming": bool(model.get("segment_underperforming", False)),
        "segment_outperforming": bool(model.get("segment_outperforming", False)),
        "dynamic_above_protected_baseline": above_protected,
        "dynamic_below_protected_baseline": below_protected,
        "baseline_regression_blocked": regression_blocked,
        "baseline_protection_reason": protection_reason,
        "shadow_decision_label": decision,
        "strongest_LR_feature": strongest["feature"],
        "strongest_LR_multiplier": strongest["multiplier"],
        "strongest_LR_reason": strongest["reason"],
        "LR_feature_count": strongest["count"],
        "missing_LR_feature_count": strongest["missing_count"],
        "baseline_vs_dynamic_status": f"{current_status}_to_{status}",
        "dynamic_signal_status": status,
        "dynamic_odds_mode": SHADOW_ONLY,
        "lr_model_loaded": model_loaded,
        "lr_model_source": model.get("model_source", "no_model"),
        "lr_model_last_trained_at_utc": model.get("last_trained_at_utc", ""),
        "model_quality_label": quality,
        "model_quality_reason": model.get("model_quality_reason", ""),
        "baseline_protection_active": bool(model.get("baseline_protection_active", False)),
        "completed_rows_seen": int(model.get("completed_rows_seen") or 0),
        "wins": int(model.get("wins") or 0),
        "losses": int(model.get("losses") or 0),
        "pushes_excluded": int(model.get("pushes_excluded") or 0),
        "lr_training_rows_used": int(model.get("training_rows") or model.get("training_rows_used") or 0),
        "lr_feature_count": int(model.get("feature_count") or 0),
        "strong_feature_count": int(model.get("strong_feature_count") or 0),
        "weak_feature_count": int(model.get("weak_feature_count") or 0),
        "insufficient_feature_count": int(model.get("insufficient_feature_count") or 0),
        "dynamic_odds_applied_live_count": 0,
    }


def resolved_dynamic_odds_shadow_model(rows: Sequence[Mapping[str, Any]], lr_model: Mapping[str, Any] | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source_rows = [deepcopy(dict(row)) for row in list(rows or []) if isinstance(row, Mapping)]
    return _resolve_lr_model(source_rows, lr_model, config)


def build_dynamic_odds_shadow_rows(rows: Sequence[Mapping[str, Any]], lr_model: Mapping[str, Any] | None = None, config: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    source_rows = [deepcopy(dict(row)) for row in list(rows or []) if isinstance(row, Mapping)]
    model = _resolve_lr_model(source_rows, lr_model, config)
    return [build_dynamic_odds_shadow_row(row, lr_model=model, config=config) for row in source_rows]


def dynamic_odds_shadow_display_columns() -> list[str]:
    return list(DISPLAY_COLUMNS)


def dynamic_odds_feature_influence_rows(lr_model: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    return feature_influence_rows(lr_model)


def dynamic_odds_shadow_learning_summary(rows: Sequence[Mapping[str, Any]], lr_model: Mapping[str, Any] | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source_rows = [deepcopy(dict(row)) for row in list(rows or []) if isinstance(row, Mapping)]
    model = _resolve_lr_model(source_rows, lr_model, config)
    shadow_rows = [build_dynamic_odds_shadow_row(row, lr_model=model, config=config) for row in source_rows]
    statuses: dict[str, int] = {}
    decisions: dict[str, int] = {}
    for row in shadow_rows:
        status = str(row.get("dynamic_signal_status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
        decision = str(row.get("shadow_decision_label") or "unknown")
        decisions[decision] = decisions.get(decision, 0) + 1
    ev_deltas = [float(row["dynamic_EV_delta"]) for row in shadow_rows if row.get("dynamic_EV_delta") is not None]
    probability_deltas = [float(row["probability_delta"]) for row in shadow_rows if row.get("probability_delta") is not None]
    biggest_upgrade = max(shadow_rows, key=lambda row: row.get("dynamic_EV_delta") if row.get("dynamic_EV_delta") is not None else -999.0, default={})
    biggest_downgrade = min(shadow_rows, key=lambda row: row.get("dynamic_EV_delta") if row.get("dynamic_EV_delta") is not None else 999.0, default={})
    status_payload = shadow_model_status({"lr_model": model, "workspace_id": model.get("workspace_id", ""), "last_trained_at_utc": model.get("last_trained_at_utc", ""), **model}, source=str(model.get("model_source", "no_model")))
    upgraded = sum(1 for row in shadow_rows if (row.get("dynamic_EV_delta") or 0) > 0)
    downgraded = sum(1 for row in shadow_rows if (row.get("dynamic_EV_delta") or 0) < 0)
    unchanged = max(0, len(shadow_rows) - upgraded - downgraded)
    return {
        **status_payload,
        "lr_model_loaded": int(model.get("feature_count") or 0) > 0,
        "training_rows_used": int(model.get("training_rows") or model.get("training_rows_used") or 0),
        "feature_count": int(model.get("feature_count") or 0),
        "baseline_success_rate": model.get("baseline_success_rate"),
        "learning_source": model.get("model_source") or ("current_completed_rows_shadow_learning_unsaved" if int(model.get("feature_count") or 0) > 0 else "no_lr_data"),
        "leakage_guard": "ON",
        "dynamic_odds_mode": SHADOW_ONLY,
        "dynamic_odds_live_activation": "OFF",
        "dynamic_odds_applied_live": 0,
        "dynamic_odds_applied_live_count": 0,
        "dynamic_green_count": statuses.get("dynamic_green", 0),
        "dynamic_yellow_count": statuses.get("dynamic_yellow", 0),
        "dynamic_red_count": statuses.get("dynamic_red", 0),
        "no_odds_count": statuses.get("no_odds", 0),
        "no_lr_data_count": statuses.get("no_lr_data", 0),
        "average_probability_delta": _round(sum(probability_deltas) / len(probability_deltas)) if probability_deltas else None,
        "average_EV_delta": _round(sum(ev_deltas) / len(ev_deltas)) if ev_deltas else None,
        "upgraded_picks_count": upgraded,
        "downgraded_picks_count": downgraded,
        "unchanged_picks_count": unchanged,
        "dynamic_above_protected_baseline_count": sum(1 for row in shadow_rows if row.get("dynamic_above_protected_baseline")),
        "dynamic_below_protected_baseline_count": sum(1 for row in shadow_rows if row.get("dynamic_below_protected_baseline")),
        "shadow_improved_count": decisions.get("shadow_improved", 0),
        "shadow_neutral_count": decisions.get("shadow_neutral", 0),
        "shadow_regressed_count": decisions.get("shadow_regressed", 0),
        "shadow_blocked_by_baseline_guard_count": decisions.get("shadow_blocked_by_baseline_guard", 0),
        "shadow_needs_more_data_count": decisions.get("shadow_needs_more_data", 0),
        "biggest_upgraded_pick": biggest_upgrade.get("event", ""),
        "biggest_upgraded_pick_EV_delta": biggest_upgrade.get("dynamic_EV_delta"),
        "biggest_downgraded_pick": biggest_downgrade.get("event", ""),
        "biggest_downgraded_pick_EV_delta": biggest_downgrade.get("dynamic_EV_delta"),
    }


def dynamic_odds_shadow_safety_summary() -> dict[str, Any]:
    return {
        "dynamic_odds_predictor": SHADOW_ONLY,
        "dynamic_odds_live_activation": "OFF",
        "dynamic_odds_applied_live": 0,
        "dynamic_odds_applied_live_count": 0,
        "live_mutation": "FORBIDDEN",
        "model_training": "FORBIDDEN",
        "official_model_training": "FORBIDDEN",
        "live_model_training": "FORBIDDEN",
        "stored_data_mutation": "FORBIDDEN",
        "repair_activation": "OFF",
        "automatic_live_promotion": "FORBIDDEN",
        "shadow_model_training": "OFFLINE_ONLY",
    }
