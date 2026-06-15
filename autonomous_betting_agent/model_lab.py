from __future__ import annotations

from typing import Any

import pandas as pd


def recommendations_from_patterns(patterns: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for pattern in patterns or []:
        records = int(float(pattern.get('records') or 0))
        actual = float(pattern.get('actual_hit_rate') or 0.0)
        predicted = float(pattern.get('avg_predicted') or 0.0)
        smoothed = float(pattern.get('smoothed_hit_rate') or 0.0)
        edge = float(pattern.get('smoothed_edge') or 0.0)
        reliability = float(pattern.get('reliability') or 0.0)
        if records < 3:
            action = 'ignore_until_more_data'
            priority = 'low'
        elif edge >= 0.05 and reliability >= 0.45:
            action = 'raise_trust'
            priority = 'high'
        elif edge <= -0.05 and reliability >= 0.35:
            action = 'lower_trust'
            priority = 'high'
        elif abs(edge) >= 0.025:
            action = 'watch'
            priority = 'medium'
        else:
            action = 'stable'
            priority = 'low'
        rows.append({
            'area': pattern.get('area', ''),
            'area_type': pattern.get('area_type', ''),
            'records': records,
            'avg_predicted': predicted,
            'actual_hit_rate': actual,
            'smoothed_hit_rate': smoothed,
            'smoothed_edge': edge,
            'reliability': reliability,
            'recommended_action': action,
            'priority': priority,
        })
    if not rows:
        return pd.DataFrame(columns=['area', 'records', 'recommended_action', 'priority'])
    return pd.DataFrame(rows).sort_values(['priority', 'records'], ascending=[True, False])


def lab_summary(recommendations: pd.DataFrame) -> dict[str, int]:
    if recommendations is None or recommendations.empty:
        return {'raise_trust': 0, 'lower_trust': 0, 'watch': 0, 'stable': 0, 'ignore_until_more_data': 0}
    counts = recommendations.get('recommended_action', pd.Series(dtype=str)).value_counts().to_dict()
    return {key: int(counts.get(key, 0)) for key in ['raise_trust', 'lower_trust', 'watch', 'stable', 'ignore_until_more_data']}
