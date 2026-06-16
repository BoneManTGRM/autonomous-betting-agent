from __future__ import annotations

from typing import Any

import pandas as pd


def _num(value: Any) -> float | None:
    try:
        out = float(str(value).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return None
    if pd.isna(out):
        return None
    return out


def _prob(value: Any) -> float | None:
    out = _num(value)
    if out is None:
        return None
    if 1 < out <= 100:
        out = out / 100
    if 0 < out < 1:
        return out
    return None


def quality_filter_row(row: dict[str, Any], *, min_edge: float = 0.06) -> dict[str, Any]:
    p = _prob(row.get('model_probability') or row.get('model_probability_clean') or row.get('probability'))
    price = _num(row.get('decimal_price') or row.get('best_price') or row.get('odds'))
    implied = None if price is None or price <= 1 else 1 / price
    edge = None if p is None or implied is None else p - implied
    text = ' '.join(str(v or '').lower() for v in row.values())
    reasons: list[str] = []
    risk = 0
    if edge is not None and edge < min_edge:
        reasons.append('edge_below_minimum')
    if ('soccer' in text or 'fifa' in text) and p is not None and p < 0.60:
        reasons.append('soccer_low_win_probability')
    if ('soccer' in text or 'fifa' in text) and any(term in text for term in ['1-0', '2-1', 'one goal']):
        reasons.append('soccer_close_margin')
        risk += 15
    if ('tennis' in text or 'atp' in text or 'wta' in text) and any(term in text for term in ['grass', '2-1', 'tiebreak']):
        reasons.append('tennis_surface_or_close_match_risk')
        risk += 20
    if any(term in text for term in ['one run', '1-run', '5-4', '4-3']):
        reasons.append('close_score_projection')
        risk += 15
    passed = not reasons and risk < 40
    tier = 'A' if passed and p is not None and edge is not None and p >= 0.60 and edge >= min_edge else 'B' if passed else 'C'
    return {
        'quality_filter_pass': bool(passed),
        'quality_tier': tier,
        'quality_risk_score': risk,
        'reason_for_downgrade': ' | '.join(reasons),
    }


def apply_quality_filter(frame: pd.DataFrame, *, min_edge: float = 0.06) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for row in frame.to_dict(orient='records'):
        item = dict(row)
        item.update(quality_filter_row(item, min_edge=min_edge))
        rows.append(item)
    return pd.DataFrame(rows)
