from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .audit import clean_text, parse_float


@dataclass(frozen=True)
class HealthCheck:
    name: str
    passed: bool
    points: int
    max_points: int
    message: str


def _series_present(frame: pd.DataFrame, *names: str) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=bool)
    present = pd.Series([False] * len(frame), index=frame.index)
    normalized = {str(col).lower().replace(' ', '_').replace('-', '_'): col for col in frame.columns}
    for name in names:
        col = normalized.get(str(name).lower().replace(' ', '_').replace('-', '_'))
        if col is not None:
            present = present | frame[col].fillna('').astype(str).str.strip().replace({'nan': '', 'None': '', 'missing': '', 'unknown': ''}).astype(bool)
    return present


def _coverage_percent(series: pd.Series) -> float:
    if series.empty:
        return 0.0
    return round(float(series.mean() * 100.0), 2)


def _score_from_percent(percent: float, max_points: int) -> int:
    return int(round(max_points * max(0.0, min(100.0, percent)) / 100.0))


def data_health_checks(frame: pd.DataFrame) -> list[HealthCheck]:
    if frame is None or frame.empty:
        return [HealthCheck('rows_loaded', False, 0, 10, 'No rows loaded.')]
    checks: list[HealthCheck] = []
    checks.append(HealthCheck('rows_loaded', True, 10, 10, f'{len(frame)} rows loaded.'))

    odds = _series_present(frame, 'decimal_price', 'best_price', 'odds', 'price', 'american_odds')
    odds_pct = _coverage_percent(odds)
    checks.append(HealthCheck('odds_present', odds_pct >= 80, _score_from_percent(odds_pct, 20), 20, f'Odds coverage: {odds_pct:.1f}%.'))

    probability = _series_present(frame, 'model_probability', 'final_probability_value', 'final_probability', 'probability')
    prob_pct = _coverage_percent(probability)
    checks.append(HealthCheck('probability_present', prob_pct >= 80, _score_from_percent(prob_pct, 20), 20, f'Model probability coverage: {prob_pct:.1f}%.'))

    event_pick = _series_present(frame, 'event', 'game', 'match') & _series_present(frame, 'prediction', 'pick', 'selection')
    event_pct = _coverage_percent(event_pick)
    checks.append(HealthCheck('event_pick_present', event_pct >= 95, _score_from_percent(event_pct, 15), 15, f'Event/pick coverage: {event_pct:.1f}%.'))

    result = _series_present(frame, 'result_status', 'win_loss', 'pick_result', 'grade', 'outcome', 'status')
    result_pct = _coverage_percent(result)
    checks.append(HealthCheck('result_status_present', result_pct >= 25, _score_from_percent(result_pct, 10), 10, f'Result/grading coverage: {result_pct:.1f}%.'))

    api = pd.to_numeric(frame.get('api_coverage_score', pd.Series([None] * len(frame))), errors='coerce')
    if api.dropna().empty:
        api_pct = 0.0
    else:
        api_pct = round(float(api.fillna(0).clip(lower=0, upper=1).mean() * 100.0), 2)
    checks.append(HealthCheck('api_coverage', api_pct >= 50, _score_from_percent(api_pct, 10), 10, f'Average API coverage: {api_pct:.1f}%.'))

    duplicate_key = None
    if {'event', 'prediction'}.issubset(set(frame.columns)):
        duplicate_key = frame[['event', 'prediction']].fillna('').astype(str).agg('|'.join, axis=1)
    duplicate_count = int(duplicate_key.duplicated().sum()) if duplicate_key is not None else 0
    duplicate_score = 10 if duplicate_count == 0 else max(0, 10 - min(10, duplicate_count))
    checks.append(HealthCheck('duplicate_check', duplicate_count == 0, duplicate_score, 10, f'Duplicate event/pick rows: {duplicate_count}.'))

    decision = frame.get('decision', pd.Series([''] * len(frame))).fillna('').astype(str).map(clean_text)
    actionable = decision.isin(['candidate', 'strong candidate', 'strong_candidate'])
    actionable_pct = _coverage_percent(actionable)
    checks.append(HealthCheck('actionable_rows', actionable_pct > 0, min(10, max(0, int(round(actionable_pct)))), 10, f'Actionable rows: {actionable_pct:.1f}%.'))

    review = frame.get('clean_grading_status', pd.Series([''] * len(frame))).fillna('').astype(str).map(clean_text).isin(['review needed', 'review_needed'])
    review_pct = _coverage_percent(~review)
    checks.append(HealthCheck('review_risk', review_pct >= 90, _score_from_percent(review_pct, 15), 15, f'Rows not requiring review: {review_pct:.1f}%.'))
    return checks


def data_health_score(frame: pd.DataFrame) -> dict[str, Any]:
    checks = data_health_checks(frame)
    points = sum(check.points for check in checks)
    max_points = sum(check.max_points for check in checks) or 1
    score = round((points / max_points) * 100.0, 2)
    if score >= 85:
        grade = 'Excellent'
    elif score >= 70:
        grade = 'Good'
    elif score >= 50:
        grade = 'Weak'
    else:
        grade = 'Poor'
    return {'score': score, 'grade': grade, 'points': points, 'max_points': max_points, 'checks': checks}


def data_health_frame(frame: pd.DataFrame) -> pd.DataFrame:
    checks = data_health_checks(frame)
    return pd.DataFrame([check.__dict__ for check in checks])
