from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .bankroll_tracker import bankroll_summary
from .duplicate_conflicts import duplicate_conflict_summary
from .line_movement import line_movement_summary
from .quality_control import build_quality_control_report
from .result_grader import grade_summary
from .row_normalizer import normalize_frame
from .stat_validation import statistical_summary


def _date_text(value: Any) -> str:
    text = '' if value is None else str(value).strip()
    if not text:
        return ''
    return text[:10]


def filter_report_date(frame: pd.DataFrame, report_date: str) -> pd.DataFrame:
    if frame is None or frame.empty or not report_date:
        return pd.DataFrame()
    data = normalize_frame(frame)
    date_columns = [column for column in ['graded_at_utc', 'prediction_timestamp', 'locked_at_utc', 'known_start_utc'] if column in data.columns]
    if not date_columns:
        return pd.DataFrame()
    mask = pd.Series(False, index=data.index)
    for column in date_columns:
        mask = mask | data[column].apply(_date_text).eq(report_date)
    return data[mask].copy()


def build_daily_report(frame: pd.DataFrame, *, report_date: str | None = None, starting_units: float = 100.0) -> dict[str, Any]:
    normalized = normalize_frame(frame)
    selected_date = report_date or datetime.now(timezone.utc).date().isoformat()
    daily = filter_report_date(normalized, selected_date)
    report_frame = daily if not daily.empty else normalized
    quality = build_quality_control_report(report_frame, starting_units=starting_units)
    stats = statistical_summary(report_frame)
    grading = grade_summary(report_frame)
    bankroll = bankroll_summary(report_frame, starting_units=starting_units)
    duplicates = duplicate_conflict_summary(report_frame)
    movement = line_movement_summary(report_frame)
    return {
        'report_date': selected_date,
        'used_fallback_full_dataset': bool(daily.empty and not normalized.empty),
        'rows_reviewed': int(len(report_frame)),
        'statistics': stats,
        'grading': grading,
        'bankroll': bankroll,
        'duplicates': duplicates,
        'line_movement': movement,
        'quality_score': quality.get('quality_score', 0),
        'recommendations': quality.get('recommendations', []),
    }


def daily_report_markdown(report: dict[str, Any]) -> str:
    stats = report.get('statistics', {})
    grading = report.get('grading', {})
    bankroll = report.get('bankroll', {})
    duplicates = report.get('duplicates', {})
    movement = report.get('line_movement', {})
    lines = [
        '# Daily Operations Report',
        '',
        f"Report date: {report.get('report_date', '')}",
        f"Rows reviewed: {report.get('rows_reviewed', 0)}",
        f"Quality score: {report.get('quality_score', 0)}/100",
        '',
        '## Results',
        f"Wins: {stats.get('wins', 0)}",
        f"Losses: {stats.get('losses', 0)}",
        f"Pending: {grading.get('pending', 0)}",
        f"Review needed: {grading.get('review_needed', 0)}",
        f"Observed hit rate: {stats.get('observed_win_rate')}",
        '',
        '## Units',
        f"Net units: {bankroll.get('net_units', 0)}",
        f"ROI percent: {bankroll.get('roi_percent')}",
        f"Max drawdown units: {bankroll.get('max_drawdown_units', 0)}",
        '',
        '## Data Quality',
        f"Exact duplicates: {duplicates.get('exact_duplicates', 0)}",
        f"Prediction conflicts: {duplicates.get('prediction_conflicts', 0)}",
        f"Result conflicts: {duplicates.get('result_conflicts', 0)}",
        f"Line movement ready rows: {movement.get('ready', 0)}",
        '',
        '## Recommendations',
    ]
    for item in report.get('recommendations', []):
        lines.append(f'- {item}')
    if report.get('used_fallback_full_dataset'):
        lines.extend(['', 'Note: no rows matched the requested report date, so the full dataset was summarized instead.'])
    return '\n'.join(lines) + '\n'
