from __future__ import annotations

from typing import Any

import pandas as pd

from .audit import parse_float
from .row_normalizer import normalize_frame


def build_bankroll_frame(frame: pd.DataFrame, *, starting_units: float = 100.0) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = normalize_frame(frame).copy()
    sort_cols = [col for col in ['graded_at_utc', 'prediction_timestamp', 'event'] if col in data.columns]
    if sort_cols:
        data = data.sort_values(sort_cols)
    bankroll = float(starting_units)
    peak = bankroll
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(data.to_dict(orient='records'), start=1):
        profit = parse_float(row.get('profit_units')) or 0.0
        stake = parse_float(row.get('stake_units')) or 0.0
        bankroll = round(bankroll + profit, 6)
        peak = max(peak, bankroll)
        drawdown = round(peak - bankroll, 6)
        item = dict(row)
        item['sequence'] = idx
        item['stake_units_clean'] = stake
        item['profit_units_clean'] = profit
        item['bankroll_units'] = bankroll
        item['peak_bankroll_units'] = peak
        item['drawdown_units'] = drawdown
        rows.append(item)
    return pd.DataFrame(rows)


def streaks_from_results(frame: pd.DataFrame) -> dict[str, int]:
    if frame is None or frame.empty or 'result_status' not in frame.columns:
        return {'longest_win_streak': 0, 'longest_loss_streak': 0}
    best_win = best_loss = cur_win = cur_loss = 0
    for value in frame['result_status'].fillna('').astype(str).str.lower().tolist():
        if value == 'win':
            cur_win += 1
            cur_loss = 0
        elif value == 'loss':
            cur_loss += 1
            cur_win = 0
        else:
            cur_win = 0
            cur_loss = 0
        best_win = max(best_win, cur_win)
        best_loss = max(best_loss, cur_loss)
    return {'longest_win_streak': best_win, 'longest_loss_streak': best_loss}


def bankroll_summary(frame: pd.DataFrame, *, starting_units: float = 100.0) -> dict[str, Any]:
    tracked = build_bankroll_frame(frame, starting_units=starting_units)
    if tracked.empty:
        return {'rows': 0, 'starting_units': starting_units, 'ending_units': starting_units, 'net_units': 0.0, 'max_drawdown_units': 0.0, 'roi_percent': None, 'longest_win_streak': 0, 'longest_loss_streak': 0}
    total_staked = float(pd.to_numeric(tracked.get('stake_units_clean', pd.Series(dtype=float)), errors='coerce').fillna(0).sum())
    net = float(pd.to_numeric(tracked.get('profit_units_clean', pd.Series(dtype=float)), errors='coerce').fillna(0).sum())
    roi = None if total_staked <= 0 else round((net / total_staked) * 100.0, 3)
    streaks = streaks_from_results(tracked)
    return {
        'rows': int(len(tracked)),
        'starting_units': float(starting_units),
        'ending_units': round(float(tracked['bankroll_units'].iloc[-1]), 6),
        'net_units': round(net, 6),
        'total_staked_units': round(total_staked, 6),
        'max_drawdown_units': round(float(pd.to_numeric(tracked.get('drawdown_units', pd.Series(dtype=float)), errors='coerce').fillna(0).max()), 6),
        'roi_percent': roi,
        **streaks,
    }
