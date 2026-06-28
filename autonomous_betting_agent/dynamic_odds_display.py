from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.dynamic_odds_predictor import dynamic_value_metrics

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
    "dynamic_edge",
    "dynamic_no_vig_edge",
    "dynamic_EV",
    "dynamic_fair_odds",
    "dynamic_signal_status",
    "dynamic_odds_mode",
    "dynamic_odds_applied_live_count",
]


def _first_text(row: Mapping[str, Any], names: Sequence[str]) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip() and str(value).strip().lower() not in {"nan", "none"}:
            return str(value).strip()
    return ""


def _has_learned_lr(metrics: Mapping[str, Any], lr_model: Mapping[str, Any] | None) -> bool:
    model = dict(lr_model or {})
    if int(model.get("feature_count") or 0) > 0:
        return True
    for item in metrics.get("LR_breakdown", []) or []:
        if isinstance(item, Mapping) and int(item.get("sample_size") or 0) > 0 and str(item.get("reason") or "") != "no_lr_data_default_lr":
            return True
    return False


def build_dynamic_odds_shadow_row(row: Mapping[str, Any], lr_model: Mapping[str, Any] | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build one display-only Dynamic Odds row without mutating the source row."""

    source = deepcopy(dict(row or {}))
    metrics = dynamic_value_metrics(source, lr_model=lr_model, config=config)
    status = metrics.get("dynamic_signal_status") or "shadow_only"
    if metrics.get("decimal_odds") is None:
        status = "no_odds"
    elif not _has_learned_lr(metrics, lr_model):
        status = "no_lr_data"
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
        "dynamic_edge": metrics.get("dynamic_edge"),
        "dynamic_no_vig_edge": metrics.get("dynamic_no_vig_edge"),
        "dynamic_EV": metrics.get("dynamic_EV"),
        "dynamic_fair_odds": metrics.get("dynamic_fair_odds"),
        "dynamic_signal_status": status,
        "dynamic_odds_mode": SHADOW_ONLY,
        "dynamic_odds_applied_live_count": 0,
    }


def build_dynamic_odds_shadow_rows(rows: Sequence[Mapping[str, Any]], lr_model: Mapping[str, Any] | None = None, config: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    return [build_dynamic_odds_shadow_row(row, lr_model=lr_model, config=config) for row in list(rows or [])]


def dynamic_odds_shadow_display_columns() -> list[str]:
    return list(DISPLAY_COLUMNS)


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
