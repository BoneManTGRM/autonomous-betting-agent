from __future__ import annotations

from autonomous_betting_agent.local_calibration import brier_score, calibration_buckets, odds_band_summary


def test_brier_score_uses_win_loss_rows_only():
    rows = [
        {"model_probability": 0.70, "grade": "win"},
        {"model_probability": 0.60, "grade": "loss"},
        {"model_probability": 0.50, "grade": "push"},
    ]
    score = brier_score(rows)
    assert score is not None
    assert round(score, 4) == round((((0.70 - 1.0) ** 2) + ((0.60 - 0.0) ** 2)) / 2, 4)


def test_calibration_buckets_accept_percent_probabilities():
    rows = [
        {"model_probability": 70, "grade": "win"},
        {"model_probability": 72, "grade": "loss"},
    ]
    buckets = calibration_buckets(rows)
    assert len(buckets) == 1
    assert buckets[0]["sample_size"] == 2
    assert buckets[0]["bucket"] == "70%-80%"


def test_odds_band_summary_counts_resolved_rows():
    rows = [
        {"decimal_price": 1.45, "grade": "win"},
        {"decimal_price": 1.55, "grade": "loss"},
        {"decimal_price": 3.1, "grade": "win"},
        {"decimal_price": 2.0, "grade": "pending"},
    ]
    summary = odds_band_summary(rows)
    by_band = {item["odds_band"]: item for item in summary}
    assert by_band["1.30-1.59"]["sample_size"] == 2
    assert by_band["3.00+"]["sample_size"] == 1
