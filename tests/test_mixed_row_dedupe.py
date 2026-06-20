from __future__ import annotations

import pandas as pd

from autonomous_betting_agent.mixed_row_dedupe import remove_lower_detail_event_overlaps


def test_result_only_event_removed_when_detailed_event_exists():
    frame = pd.DataFrame([
        {
            'event': 'Team A at Team B',
            'prediction': 'Team B',
            'model_probability_clean': 0.64,
            'decimal_price': 1.8,
            'source_file': 'pro_predictor.csv',
        },
        {
            'event': 'Team A at Team B',
            'prediction': 'Team B',
            'result': 'won',
            'source_file': 'high_confidence_results.csv',
        },
    ])

    out = remove_lower_detail_event_overlaps(frame)

    assert len(out) == 1
    assert out.iloc[0]['source_file'] == 'pro_predictor.csv'


def test_different_detailed_market_rows_are_kept():
    frame = pd.DataFrame([
        {
            'event': 'Team A at Team B',
            'market_type': 'h2h',
            'prediction': 'Team B',
            'model_probability_clean': 0.64,
        },
        {
            'event': 'Team A at Team B',
            'market_type': 'spreads',
            'line_point': -1.5,
            'prediction': 'Team B -1.5',
            'decimal_price': 1.91,
        },
    ])

    out = remove_lower_detail_event_overlaps(frame)

    assert len(out) == 2
