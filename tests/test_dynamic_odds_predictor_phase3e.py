from __future__ import annotations

import copy

import pytest

import autonomous_betting_agent.ui_i18n_phase3d  # noqa: F401
from autonomous_betting_agent.dynamic_odds_predictor import (
    apply_lr_multipliers,
    build_phase3e_report,
    decimal_to_book_odds_ratio,
    decimal_to_raw_implied_probability,
    dynamic_value_metrics,
    evaluate_dynamic_odds_shadow,
    extract_pregame_safe_features,
    learn_lr_multipliers,
    odds_ratio_to_probability,
    recency_decay,
    split_lr_train_evaluation_rows,
)
from autonomous_betting_agent.reparodynamics_repair_memory import update_repair_memory
from autonomous_betting_agent.ui_i18n import localize_dataframe


def _row(index: int, *, result: str = "win", odds: float = 2.0, prob: float = 0.55, ts_prefix: str = "2026-01") -> dict:
    day = (index % 28) + 1
    return {
        "row_id": f"row_{index}",
        "event_id": f"event_{index}",
        "sport": "soccer",
        "league": "mx_test",
        "market_type": "moneyline",
        "sportsbook": "testbook",
        "decimal_price": odds,
        "model_probability": prob,
        "result": result,
        "locked_at_utc": f"{ts_prefix}-{day:02d}T12:00:00Z",
    }


def _rows(count: int = 120) -> list[dict]:
    rows = []
    for index in range(count):
        result = "win" if index % 3 != 0 else "loss"
        odds = 2.2 if index % 2 == 0 else 1.9
        prob = 0.58 if index % 2 == 0 else 0.53
        rows.append(_row(index, result=result, odds=odds, prob=prob))
    return rows


def _loose_config() -> dict:
    return {
        "minimum_lr_sample": 2,
        "strong_lr_sample": 4,
        "minimum_lr_training_rows": 5,
        "minimum_lr_evaluation_rows": 3,
        "minimum_completed_rows_for_evaluation": 3,
        "minimum_dynamic_edge": -0.50,
        "minimum_dynamic_no_vig_edge": -0.50,
        "minimum_dynamic_EV": -0.50,
    }


def test_decimal_and_odds_ratio_math():
    assert decimal_to_raw_implied_probability(3.0) == pytest.approx(1 / 3)
    assert decimal_to_book_odds_ratio(3.0) == pytest.approx(0.5)
    assert odds_ratio_to_probability(1.5) == pytest.approx(0.6)


def test_apply_lr_multipliers_example_and_decay():
    applied = apply_lr_multipliers(0.5, [{"capped_lr": 2.0}, {"capped_lr": 1.5}], data_age_hours=0, lambda_value=0)
    assert applied["dynamic_probability"] == pytest.approx(0.6)
    decayed = apply_lr_multipliers(0.5, [{"capped_lr": 2.0}, {"capped_lr": 1.5}], data_age_hours=10, lambda_value=0.1)
    assert decayed["dynamic_odds_ratio"] < applied["dynamic_odds_ratio"]
    assert recency_decay(10, 0.1) < 1.0


def test_missing_odds_creates_no_odds_not_green():
    metrics = dynamic_value_metrics({"result": "win", "model_probability": 0.6})
    assert metrics["dynamic_signal_status"] == "no_odds"


def test_pregame_safe_feature_extraction_blocks_leakage_fields_and_does_not_mutate_input():
    row = _row(1)
    row.update({"profit_units": 1.2, "ROI": 0.4, "postgame_stats": "late", "final_result": "win"})
    before = copy.deepcopy(row)
    extracted = extract_pregame_safe_features(row)
    assert row == before
    assert any("profit" in key.lower() for key in extracted["blocked_leakage_fields"])
    assert any("roi" in key.lower() for key in extracted["blocked_leakage_fields"])
    assert "sport" in extracted["features"]


def test_lr_defaults_and_caps_are_safe():
    model = learn_lr_multipliers([_row(1, result="win"), _row(2, result="loss")])
    assert all(item["capped_lr"] == pytest.approx(1.0) for item in model["lr_by_feature"].values())
    capped = learn_lr_multipliers(_rows(60), {"minimum_lr_sample": 2, "strong_lr_sample": 2, "max_LR": 1.1, "min_LR": 0.9})
    assert all(0.9 <= item["capped_lr"] <= 1.1 for item in capped["lr_by_feature"].values())


def test_dynamic_value_metrics_edge_no_vig_and_ev():
    metrics = dynamic_value_metrics({"decimal_price": 3.0, "model_probability": 0.4, "no_vig_implied_probability": 0.30}, dynamic_probability=0.60)
    assert metrics["dynamic_edge"] == pytest.approx(0.60 - (1 / 3))
    assert metrics["dynamic_no_vig_edge"] == pytest.approx(0.30)
    assert metrics["dynamic_EV"] == pytest.approx(0.8)
    assert metrics["dynamic_signal_status"] == "dynamic_green"


def test_dynamic_probability_does_not_replace_model_probability():
    row = {"decimal_price": 3.0, "model_probability": 0.4, "result": "win"}
    before = copy.deepcopy(row)
    metrics = dynamic_value_metrics(row, dynamic_probability=0.60)
    assert row == before
    assert metrics["current_model_probability"] == pytest.approx(0.4)
    assert row["model_probability"] == 0.4


def test_chronological_split_and_stable_hash_holdout():
    rows = _rows(20)
    split = split_lr_train_evaluation_rows(rows, {"minimum_lr_training_rows": 5, "minimum_lr_evaluation_rows": 3})
    assert split["evaluation_mode"] == "chronological_holdout"
    assert split["train_test_overlap_count"] == 0
    no_time = [{key: value for key, value in row.items() if key != "locked_at_utc"} for row in rows]
    first = split_lr_train_evaluation_rows(no_time)
    second = split_lr_train_evaluation_rows(no_time)
    assert first["evaluation_mode"] == "stable_hash_holdout"
    assert [row["row_id"] for row in first["evaluation_rows"]] == [row["row_id"] for row in second["evaluation_rows"]]


def test_evaluate_dynamic_odds_shadow_report_safety_and_leakage_guard():
    report = evaluate_dynamic_odds_shadow(_rows(80), _loose_config())
    assert report["leakage_guard_enabled"] is True
    assert report["train_test_overlap_count"] == 0
    assert report["baseline_metrics"]
    assert report["dynamic_metrics"]
    assert report["comparison_metrics"]


def test_too_few_rows_cannot_reach_future_manual_review():
    report = evaluate_dynamic_odds_shadow(_rows(4))
    assert report["decision"] in {"keep_testing", "data_blocked"}


def test_phase3e_report_is_shadow_only_and_memory_dedupes():
    phase3e = build_phase3e_report(_rows(80), _loose_config())
    assert phase3e["phase"] == "Phase 3E Dynamic Odds Predictor Shadow"
    assert phase3e["dynamic_odds_applied_live_count"] == 0
    assert phase3e["dynamic_odds_live_activation"] == "OFF"
    assert phase3e["live_mutation"] == "FORBIDDEN"
    assert phase3e["model_training"] == "FORBIDDEN"
    assert phase3e["stored_data_mutation"] == "FORBIDDEN"
    memory = update_repair_memory(None, phase3e)
    memory = update_repair_memory(memory, phase3e)
    item = next(iter(memory["items"].values()))
    assert item["times_seen"] == 1
    assert memory["last_save_status"] == "already_saved"


def test_future_manual_review_still_shadow_only_when_reached():
    rows = []
    for index in range(100):
        rows.append(_row(index, result="win", odds=2.5, prob=0.40))
    report = build_phase3e_report(rows, _loose_config())
    assert report["dynamic_odds_applied_live_count"] == 0
    assert report["dynamic_odds_live_activation"] == "OFF"
    assert report["safety_gates"]["live_mutation"] == "FORBIDDEN"


def test_no_safe_lr_features_still_calculates_with_default_lr():
    metrics = dynamic_value_metrics({"decimal_price": 2.0, "model_probability": 0.55, "result": "win"}, lr_model={"lr_by_feature": {}})
    assert metrics["dynamic_probability"] is not None
    assert all(item["capped_lr"] == 1.0 for item in metrics["LR_breakdown"])


def test_spanish_localization_for_phase3e_columns_and_values():
    import pandas as pd

    df = pd.DataFrame([{"dynamic_probability": 0.6, "dynamic_signal_status": "dynamic_green"}])
    localized = localize_dataframe(df, "es")
    assert "Probabilidad dinamica" in localized.columns or "dynamic_probability" in localized.columns
