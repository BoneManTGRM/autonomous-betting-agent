from __future__ import annotations

import pandas as pd

from autonomous_betting_agent.profit_guard import add_profit_guard, filter_profit_guard


def test_profit_guard_keeps_volume_but_removes_bad_prices() -> None:
    frame = pd.DataFrame([
        {'model_probability_clean': 0.70, 'decimal_price': 1.50, 'market_implied_probability': 0.667, 'model_market_edge': 0.033, 'pattern_points': 72},
        {'model_probability_clean': 0.68, 'decimal_price': 1.42, 'market_implied_probability': 0.704, 'model_market_edge': -0.024, 'pattern_points': 70},
        {'model_probability_clean': 0.82, 'decimal_price': 1.08, 'market_implied_probability': 0.926, 'model_market_edge': -0.106, 'pattern_points': 85},
        {'model_probability_clean': 0.55, 'decimal_price': 5.50, 'market_implied_probability': 0.182, 'model_market_edge': 0.368, 'pattern_points': 60},
    ])
    guarded = add_profit_guard(frame)
    assert 'profit_guard_status' in guarded.columns
    assert 'profit_protection_score' in guarded.columns
    assert len(filter_profit_guard(guarded, 'Research no profit guard')) == 4
    assert len(filter_profit_guard(guarded, 'Volume-safe profit guard')) == 2
    assert len(filter_profit_guard(guarded, 'Official ROI guard')) <= len(filter_profit_guard(guarded, 'Balanced ROI guard'))
