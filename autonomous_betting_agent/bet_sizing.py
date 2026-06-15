from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from .audit import parse_float
from .pick_quality import build_pick_quality_frame


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


def probability(value: Any) -> float | None:
    number = parse_float(value)
    if number is None:
        return None
    if 1.0 < number <= 100.0:
        number /= 100.0
    return number if 0.0 < number < 1.0 else None


def conservative_kelly_fraction(probability_value: float | None, decimal_price: float | None) -> float:
    if probability_value is None or decimal_price is None or decimal_price <= 1.0:
        return 0.0
    b = decimal_price - 1.0
    q = 1.0 - probability_value
    full_kelly = ((b * probability_value) - q) / b
    if full_kelly <= 0:
        return 0.0
    # Quarter Kelly capped at 2% bankroll exposure.
    return min(0.02, full_kelly * 0.25)


def smart_stake_for_row(row: Mapping[str, Any], *, max_units: float = 2.0) -> dict[str, Any]:
    prob = probability(_first(row, 'model_probability', 'final_probability', 'final_probability_value', 'probability'))
    price = parse_float(_first(row, 'decimal_price', 'best_price', 'odds'))
    quality = parse_float(_first(row, 'pick_quality_score'))
    grade = _safe(_first(row, 'pick_quality_grade', 'confidence_tier')).lower()
    lock_status = _safe(_first(row, 'lock_status')).lower()
    review_status = _safe(_first(row, 'review_status', 'clean_grading_status')).lower()
    decision = _safe(_first(row, 'decision')).lower()

    reasons: list[str] = []
    if prob is None or price is None:
        return {'kelly_fraction': 0.0, 'recommended_units': 0.0, 'stake_bucket': 'No Bet', 'stake_reason': 'Missing probability or odds.'}
    if lock_status and lock_status != 'official_locked':
        return {'kelly_fraction': 0.0, 'recommended_units': 0.0, 'stake_bucket': 'No Bet', 'stake_reason': 'Not official locked.'}
    if review_status in {'review_needed', 'review needed'}:
        return {'kelly_fraction': 0.0, 'recommended_units': 0.0, 'stake_bucket': 'No Bet', 'stake_reason': 'Manual review needed.'}
    if 'watch' in decision or 'skip' in decision or 'no_bet' in decision:
        return {'kelly_fraction': 0.0, 'recommended_units': 0.0, 'stake_bucket': 'No Bet', 'stake_reason': 'Decision is not actionable.'}

    kelly = conservative_kelly_fraction(prob, price)
    if kelly <= 0:
        return {'kelly_fraction': 0.0, 'recommended_units': 0.0, 'stake_bucket': 'No Bet', 'stake_reason': 'No positive edge by conservative Kelly.'}

    quality_multiplier = 1.0
    if quality is not None:
        if quality >= 90:
            quality_multiplier = 1.0
            reasons.append('Elite quality.')
        elif quality >= 80:
            quality_multiplier = 0.75
            reasons.append('Strong quality.')
        elif quality >= 65:
            quality_multiplier = 0.45
            reasons.append('Playable quality.')
        else:
            quality_multiplier = 0.0
            reasons.append('Quality too low.')
    elif 'a+ high' in grade:
        quality_multiplier = 1.0
    elif 'a strong' in grade:
        quality_multiplier = 0.75
    elif 'b lean' in grade:
        quality_multiplier = 0.45
    else:
        quality_multiplier = 0.25

    units = round(max_units * (kelly / 0.02) * quality_multiplier, 2)
    units = max(0.0, min(max_units, units))
    if units >= 1.5:
        bucket = 'Strong Stake'
    elif units >= 0.75:
        bucket = 'Standard Stake'
    elif units >= 0.25:
        bucket = 'Small Stake'
    else:
        bucket = 'No Bet'
        units = 0.0
    reasons.append(f'Quarter Kelly fraction {kelly:.4f}.')
    return {'kelly_fraction': round(kelly, 6), 'recommended_units': units, 'stake_bucket': bucket, 'stake_reason': ' '.join(reasons)}


def build_bet_sizing_frame(frame: pd.DataFrame, *, max_units: float = 2.0, score_quality: bool = True) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    source = build_pick_quality_frame(frame) if score_quality and 'pick_quality_score' not in frame.columns else frame.copy()
    rows: list[dict[str, Any]] = []
    for raw in source.to_dict(orient='records'):
        item = dict(raw)
        item.update(smart_stake_for_row(raw, max_units=max_units))
        rows.append(item)
    return pd.DataFrame(rows).sort_values(['recommended_units', 'pick_quality_score' if 'pick_quality_score' in source.columns else source.columns[0]], ascending=[False, False])


def bet_sizing_summary(frame: pd.DataFrame) -> dict[str, Any]:
    sized = build_bet_sizing_frame(frame)
    if sized.empty:
        return {'rows': 0, 'total_units': 0.0, 'strong': 0, 'standard': 0, 'small': 0, 'no_bet': 0}
    buckets = sized.get('stake_bucket', pd.Series(dtype=str)).value_counts().to_dict()
    return {
        'rows': int(len(sized)),
        'total_units': round(float(pd.to_numeric(sized.get('recommended_units', pd.Series(dtype=float)), errors='coerce').fillna(0).sum()), 2),
        'strong': int(buckets.get('Strong Stake', 0)),
        'standard': int(buckets.get('Standard Stake', 0)),
        'small': int(buckets.get('Small Stake', 0)),
        'no_bet': int(buckets.get('No Bet', 0)),
    }
