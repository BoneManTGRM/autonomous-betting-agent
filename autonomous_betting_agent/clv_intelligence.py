from __future__ import annotations

from typing import Any

import pandas as pd

from .audit import parse_float
from .row_normalizer import normalize_frame, result_status


def clv_row(row: dict[str, Any]) -> dict[str, Any]:
    locked = parse_float(row.get('decimal_price'))
    closing = parse_float(row.get('closing_decimal_price'))
    if locked is None or locked <= 1 or closing is None or closing <= 1:
        return {
            'clv_ready': False,
            'clv_decimal_delta': None,
            'clv_percent': None,
            'clv_signal': 'missing',
            'beat_close': False,
        }
    delta = round(locked - closing, 6)
    pct = round((locked / closing - 1.0) * 100.0, 4)
    if delta > 0:
        signal = 'positive'
    elif delta < 0:
        signal = 'negative'
    else:
        signal = 'neutral'
    return {
        'clv_ready': True,
        'clv_decimal_delta': delta,
        'clv_percent': pct,
        'clv_signal': signal,
        'beat_close': delta > 0,
    }


def build_clv_intelligence(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = normalize_frame(frame)
    rows: list[dict[str, Any]] = []
    for row in data.to_dict(orient='records'):
        item = dict(row)
        item.update(clv_row(row))
        item['resolved_status'] = result_status(row)
        rows.append(item)
    return pd.DataFrame(rows)


def clv_summary(frame: pd.DataFrame) -> dict[str, Any]:
    clv = build_clv_intelligence(frame)
    if clv.empty:
        return {'rows': 0, 'ready': 0, 'positive': 0, 'negative': 0, 'neutral': 0, 'avg_clv_percent': None, 'beat_close_rate': None}
    ready = clv[clv['clv_ready'].astype(bool)] if 'clv_ready' in clv else pd.DataFrame()
    if ready.empty:
        return {'rows': int(len(clv)), 'ready': 0, 'positive': 0, 'negative': 0, 'neutral': 0, 'avg_clv_percent': None, 'beat_close_rate': None}
    signal = ready['clv_signal'].fillna('').astype(str)
    return {
        'rows': int(len(clv)),
        'ready': int(len(ready)),
        'positive': int(signal.eq('positive').sum()),
        'negative': int(signal.eq('negative').sum()),
        'neutral': int(signal.eq('neutral').sum()),
        'avg_clv_percent': round(float(pd.to_numeric(ready['clv_percent'], errors='coerce').fillna(0).mean()), 4),
        'beat_close_rate': round(float(ready['beat_close'].astype(bool).mean()), 6),
    }


def clv_by_segment(frame: pd.DataFrame, segment: str = 'sport') -> pd.DataFrame:
    clv = build_clv_intelligence(frame)
    if clv.empty or segment not in clv.columns:
        return pd.DataFrame(columns=[segment, 'rows', 'ready', 'positive', 'negative', 'avg_clv_percent', 'beat_close_rate'])
    rows: list[dict[str, Any]] = []
    for value, group in clv.groupby(segment, dropna=False):
        ready = group[group['clv_ready'].astype(bool)] if 'clv_ready' in group else pd.DataFrame()
        if ready.empty:
            rows.append({segment: value, 'rows': int(len(group)), 'ready': 0, 'positive': 0, 'negative': 0, 'avg_clv_percent': None, 'beat_close_rate': None})
            continue
        signal = ready['clv_signal'].fillna('').astype(str)
        rows.append({
            segment: value,
            'rows': int(len(group)),
            'ready': int(len(ready)),
            'positive': int(signal.eq('positive').sum()),
            'negative': int(signal.eq('negative').sum()),
            'avg_clv_percent': round(float(pd.to_numeric(ready['clv_percent'], errors='coerce').fillna(0).mean()), 4),
            'beat_close_rate': round(float(ready['beat_close'].astype(bool).mean()), 6),
        })
    return pd.DataFrame(rows).sort_values(['ready', 'beat_close_rate'], ascending=False)
