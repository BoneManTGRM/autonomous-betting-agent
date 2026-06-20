import json

import pandas as pd

from autonomous_betting_agent.adaptive_learning import apply_adaptive_learning, learning_drift_summary, threshold_suggestions


def test_adaptive_learning_boosts_matching_positive_pattern(tmp_path):
    memory = {
        "patterns": [
            {
                "area_type": "sport_market",
                "group_value": "nba|spreads",
                "records": 120,
                "smoothed_edge": 0.08,
                "roi": 0.10,
                "reliability": 0.9,
            }
        ]
    }
    path = tmp_path / "learning_memory_bank.json"
    path.write_text(json.dumps(memory), encoding="utf-8")
    frame = pd.DataFrame([
        {
            "sport": "NBA",
            "market_type": "spreads",
            "model_probability_clean": 0.62,
            "model_market_edge": 0.03,
            "decimal_price": 1.91,
            "books": 20,
            "api_coverage_score": 1.0,
            "agent_score": 50,
        }
    ])

    out = apply_adaptive_learning(frame, memory_path=path)

    assert out.loc[0, "learning_pattern_count"] >= 1
    assert out.loc[0, "learning_adjustment_score"] > 0
    assert out.loc[0, "learned_agent_score"] > 50
    assert out.loc[0, "recommended_stake_units"] >= 0.10


def test_adaptive_learning_penalizes_matching_negative_pattern(tmp_path):
    memory = {
        "patterns": [
            {
                "area_type": "sport_market",
                "group_value": "nba|totals",
                "records": 120,
                "smoothed_edge": -0.08,
                "reliability": 0.9,
            }
        ]
    }
    path = tmp_path / "learning_memory_bank.json"
    path.write_text(json.dumps(memory), encoding="utf-8")
    frame = pd.DataFrame([
        {
            "sport": "NBA",
            "market_type": "totals",
            "model_probability_clean": 0.62,
            "model_market_edge": 0.03,
            "decimal_price": 1.91,
            "books": 20,
            "api_coverage_score": 1.0,
            "agent_score": 50,
        }
    ])

    out = apply_adaptive_learning(frame, memory_path=path)

    assert out.loc[0, "learning_pattern_count"] >= 1
    assert out.loc[0, "learning_adjustment_score"] < 0
    assert out.loc[0, "learned_agent_score"] < 50


def test_adaptive_learning_blocks_strong_negative_roi_pattern(tmp_path):
    memory = {
        "patterns": [
            {
                "area_type": "sport_market",
                "group_value": "mlb|h2h",
                "records": 75,
                "smoothed_edge": -0.07,
                "roi": -0.12,
                "profit_units": -12,
                "reliability": 0.75,
            }
        ]
    }
    path = tmp_path / "learning_memory_bank.json"
    path.write_text(json.dumps(memory), encoding="utf-8")
    frame = pd.DataFrame([
        {
            "sport": "MLB",
            "market_type": "h2h",
            "model_probability_clean": 0.64,
            "model_market_edge": 0.04,
            "decimal_price": 1.85,
            "books": 15,
            "api_coverage_score": 1.0,
            "agent_score": 70,
        }
    ])

    out = apply_adaptive_learning(frame, memory_path=path)

    assert bool(out.loc[0, "learning_blocked"]) is True
    assert out.loc[0, "learning_action"] == "block_or_review"
    assert out.loc[0, "recommended_stake_units"] == 0.0


def test_threshold_suggestions_returns_preferred_and_avoid_patterns(tmp_path):
    memory = {
        "patterns": [
            {"area_type": "sport_market", "group_value": "nba|spreads", "area": "NBA / spreads", "records": 60, "smoothed_edge": 0.05, "roi": 0.09, "reliability": 0.8},
            {"area_type": "market_type", "group_value": "totals", "area": "Market: totals", "records": 60, "smoothed_edge": -0.06, "roi": -0.10, "reliability": 0.8},
        ]
    }
    path = tmp_path / "learning_memory_bank.json"
    path.write_text(json.dumps(memory), encoding="utf-8")

    suggestions = threshold_suggestions(path)

    assert suggestions["positive_pattern_count"] == 1
    assert suggestions["negative_pattern_count"] == 1
    assert "nba|spreads" in suggestions["preferred_markets"]
    assert suggestions["avoid_patterns"]


def test_drift_summary_detects_recent_improvement(tmp_path):
    compact_rows = []
    for index in range(60):
        compact_rows.append({"probability": 0.60, "outcome": 0 if index < 40 else 1, "start": f"2026-01-{(index % 28) + 1:02d}T00:00:00Z"})
    memory = {"patterns": [], "compact_rows": compact_rows}
    path = tmp_path / "learning_memory_bank.json"
    path.write_text(json.dumps(memory), encoding="utf-8")

    drift = learning_drift_summary(path)

    assert drift["rows"] == 60
    assert drift["status"] in {"recent_improving", "stable", "recent_declining"}
    assert "score_adjustment" in drift
    assert abs(drift["score_adjustment"]) <= 3.0


def test_adaptive_learning_applies_small_drift_adjustment_without_blocking(tmp_path):
    compact_rows = []
    for index in range(60):
        compact_rows.append({"probability": 0.60, "outcome": 1 if index >= 40 else 0, "start": f"2026-02-{(index % 28) + 1:02d}T00:00:00Z"})
    memory = {
        "compact_rows": compact_rows,
        "patterns": [
            {"area_type": "sport_market", "group_value": "nba|spreads", "records": 60, "effective_records": 60, "smoothed_edge": 0.02, "roi": 0.02, "reliability": 0.6}
        ],
    }
    path = tmp_path / "learning_memory_bank.json"
    path.write_text(json.dumps(memory), encoding="utf-8")
    frame = pd.DataFrame([{"sport": "NBA", "market_type": "spreads", "model_probability_clean": 0.62, "agent_score": 55}])

    out = apply_adaptive_learning(frame, memory_path=path)

    assert "learning_drift_adjustment" in out.columns
    assert abs(out.loc[0, "learning_drift_adjustment"]) <= 3.0
    assert bool(out.loc[0, "learning_blocked"]) is False


def test_adaptive_learning_without_memory_keeps_base_score(tmp_path):
    frame = pd.DataFrame([{"agent_score": 55, "model_probability_clean": 0.61, "recommended_stake_units": 0.10}])

    out = apply_adaptive_learning(frame, memory_path=tmp_path / "missing.json")

    assert out.loc[0, "learning_pattern_count"] == 0
    assert out.loc[0, "learning_adjustment_score"] == 0.0
    assert out.loc[0, "learned_agent_score"] == 55
    assert out.loc[0, "recommended_stake_units"] == 0.10
