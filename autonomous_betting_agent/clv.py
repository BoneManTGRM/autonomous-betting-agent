from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from .audit import parse_float


def _safe(value: Any) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    return str(value).strip()


def _first(row: Mapping[str, Any], *names: str) -> Any:
    normalized = {str(key).lower().replace(' ', '_').replace('-', '_'): value for key, value in row.items()}
    for name in names:
        value = normalized.get(name.lower().replace(' ', '_').replace('-', '_'))
        if _safe(value):
            return value
    return ''


def implied_probability(decimal_price: float | None) -> float | None:
    if decimal_price is None or decimal_price <= 1.0:
        return None
    return 1.0 / decimal_price


def clv_for_row(row: Mapping[str, Any]) -> dict[str, Any]:
    locked = parse_float(_first(row, 'locked_decimal_price', 'prediction_decimal_price', 'decimal_price', 'best_price'))
    closing = parse_float(_first(row, 'closing_decimal_price', 'closing_price', 'close_decimal', 'closing_odds'))
    locked_imp = implied_probability(locked)
    closing_imp = implied_probability(closing)
    if locked is None or closing is None or locked_imp is None or closing_imp is None:
        status = 'missing_closing_or_locked_odds'
        clv_decimal = None
        clv_probability = None
        positive = None
    else:
        clv_decimal = closing - locked
        clv_probability = locked_imp - closing_imp
        positive = clv_probability > 0
        status = 'positive_clv' if positive else 'negative_or_flat_clv'
    return {
        'locked_decimal_price': locked,
        'closing_decimal_price': closing,
        'locked_implied_probability': locked_imp,
        'closing_implied_probability': closing_imp,
        'clv_decimal_move': clv_decimal,
        'clv_probability_edge': clv_probability,
        'clv_positive': positive,
        'clv_status': status,
    }


def build_clv_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient='records'):
        item = dict(raw)
        item.update(clv_for_row(raw))
        rows.append(item)
    return pd.DataFrame(rows)


def clv_summary(frame: pd.DataFrame) -> dict[str, Any]:
    out = build_clv_frame(frame)
    if out.empty:
        return {'rows': 0, 'with_clv': 0, 'positive_clv': 0, 'positive_clv_rate': None, 'avg_clv_probability_edge': None}
    with_clv = out[out['clv_positive'].isin([True, False])]
    positive = int((with_clv['clv_positive'] == True).sum()) if not with_clv.empty else 0
    avg_edge = pd.to_numeric(with_clv.get('clv_probability_edge', pd.Series(dtype=float)), errors='coerce').dropna()
    return {
        'rows': int(len(out)),
        'with_clv': int(len(with_clv)),
        'positive_clv': positive,
        'positive_clv_rate': None if with_clv.empty else positive / len(with_clv),
        'avg_clv_probability_edge': None if avg_edge.empty else float(avg_edge.mean()),
    }
