from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.dynamic_odds_predictor import dynamic_value_metrics, learn_lr_multipliers
from autonomous_betting_agent.dynamic_odds_shadow_memory import (
    infer_workspace_id,
    load_dynamic_odds_shadow_model,
    runtime_lr_model,
    shadow_model_status,
    train_and_save_dynamic_odds_shadow_model,
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
    "lr_training_rows_used",
    "lr_feature_count",
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
    "push",
    "void",
    "cancel",
    "cancelled",
    "canceled",
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
    completed = [deepcopy(dict(row)) for row in rows or [] if isinstance(row, Mapping) and _is_completed_row(row)]
    model = learn_lr_multipliers(completed, config) if completed else learn_lr_multipliers([], config)
    model["model_source"] = "current_completed_rows_shadow_learning" if completed else "no_lr_data"
    model["last_trained_at_utc"] = ""
    model["dynamic_odds_applied_live_count"] = 0
    return model


def _resolve_lr_model(rows: Sequence[Mapping[str, Any]] | None, lr_model: Mapping[str, Any] | None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
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
    completed = [row for row in source_rows if _is_completed_row(row)]
    if completed:
        try:
            saved_payload = train_and_save_dynamic_odds_shadow_model(completed, workspace_id=workspace_id, config=config, source="graded_rows_seen_in_shadow_panel")
            return runtime_lr_model(saved_payload)
        except Exception:
            return _lr_model_from_rows(completed, config)
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
        "dynamic_probability": metrics.get("dynamic_probability"),
        "probability_delta": _round(probability_delta),
        "dynamic_edge": metrics.get("dynamic_edge"),
        "current_edge": metrics.get("current_edge"),
        "dynamic_edge_delta": _round(dynamic_edge_delta),
        "dynamic_no_vig_edge": metrics.get("dynamic_no_vig_edge"),
        "dynamic_EV": metrics.get("dynamic_EV"),
        "current_EV": metrics.get("current_EV"),
        "dynamic_EV_delta": _round(dynamic_ev_delta),
        "dynamic_fair_odds": metrics.get("dynamic_fair_odds"),
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
        "lr_training_rows_used": int(model.get("training_rows") or 0),
        "lr_feature_count": int(model.get("feature_count") or 0),
        "dynamic_odds_applied_live_count": 0,
    }


def build_dynamic_odds_shadow_rows(rows: Sequence[Mapping[str, Any]], lr_model: Mapping[str, Any] | None = None, config: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    source_rows = [deepcopy(dict(row)) for row in list(rows or []) if isinstance(row, Mapping)]
    model = _resolve_lr_model(source_rows, lr_model, config)
    return [build_dynamic_odds_shadow_row(row, lr_model=model, config=config) for row in source_rows]


def dynamic_odds_shadow_display_columns() -> list[str]:
    return list(DISPLAY_COLUMNS)


def dynamic_odds_shadow_learning_summary(rows: Sequence[Mapping[str, Any]], lr_model: Mapping[str, Any] | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source_rows = [deepcopy(dict(row)) for row in list(rows or []) if isinstance(row, Mapping)]
    model = _resolve_lr_model(source_rows, lr_model, config)
    shadow_rows = [build_dynamic_odds_shadow_row(row, lr_model=model, config=config) for row in source_rows]
    statuses: dict[str, int] = {}
    for row in shadow_rows:
        status = str(row.get("dynamic_signal_status") or "unknown")
        statuses[status] = statuses.get(status, 0) + 1
    ev_deltas = [float(row["dynamic_EV_delta"]) for row in shadow_rows if row.get("dynamic_EV_delta") is not None]
    probability_deltas = [float(row["probability_delta"]) for row in shadow_rows if row.get("probability_delta") is not None]
    biggest_upgrade = max(shadow_rows, key=lambda row: row.get("dynamic_EV_delta") if row.get("dynamic_EV_delta") is not None else -999.0, default={})
    biggest_downgrade = min(shadow_rows, key=lambda row: row.get("dynamic_EV_delta") if row.get("dynamic_EV_delta") is not None else 999.0, default={})
    status_payload = shadow_model_status({"lr_model": model, "workspace_id": model.get("workspace_id", ""), "last_trained_at_utc": model.get("last_trained_at_utc", "")}, source=str(model.get("model_source", "no_model")))
    return {
        **status_payload,
        "lr_model_loaded": int(model.get("feature_count") or 0) > 0,
        "training_rows_used": int(model.get("training_rows") or 0),
        "feature_count": int(model.get("feature_count") or 0),
        "baseline_success_rate": model.get("baseline_success_rate"),
        "learning_source": model.get("model_source") or ("current_completed_rows_shadow_learning" if int(model.get("feature_count") or 0) > 0 else "no_lr_data"),
        "leakage_guard": "ON",
        "dynamic_odds_mode": SHADOW_ONLY,
        "dynamic_odds_live_activation": "OFF",
        "dynamic_odds_applied_live_count": 0,
        "dynamic_green_count": statuses.get("dynamic_green", 0),
        "dynamic_yellow_count": statuses.get("dynamic_yellow", 0),
        "dynamic_red_count": statuses.get("dynamic_red", 0),
        "no_odds_count": statuses.get("no_odds", 0),
        "no_lr_data_count": statuses.get("no_lr_data", 0),
        "average_probability_delta": _round(sum(probability_deltas) / len(probability_deltas)) if probability_deltas else None,
        "average_EV_delta": _round(sum(ev_deltas) / len(ev_deltas)) if ev_deltas else None,
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
        "stored_data_mutation": "FORBIDDEN",
        "repair_activation": "OFF",
        "automatic_live_promotion": "FORBIDDEN",
    }
