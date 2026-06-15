from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd

from .row_normalizer import normalize_frame, safe_text


def _norm(value: Any) -> str:
    return safe_text(value).lower().strip()


def row_key(row: dict[str, Any], fields: list[str]) -> str:
    raw = '|'.join(_norm(row.get(field)) for field in fields)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


def build_duplicate_conflict_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    data = normalize_frame(frame).copy()
    records = data.to_dict(orient='records')
    event_keys = [row_key(row, ['event', 'sport', 'market_type']) for row in records]
    pick_keys = [row_key(row, ['event', 'sport', 'market_type', 'prediction']) for row in records]
    exact_keys = [row_key(row, ['event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price']) for row in records]
    data['event_key'] = event_keys
    data['pick_key'] = pick_keys
    data['exact_key'] = exact_keys
    data['duplicate_exact_count'] = data.groupby('exact_key')['exact_key'].transform('count')
    data['duplicate_pick_count'] = data.groupby('pick_key')['pick_key'].transform('count')
    data['event_row_count'] = data.groupby('event_key')['event_key'].transform('count')

    conflict_predictions = data.groupby('event_key')['prediction'].transform(lambda series: series.fillna('').astype(str).str.strip().replace('', pd.NA).dropna().nunique())
    conflict_results = data.groupby('event_key')['result_status'].transform(lambda series: series.fillna('').astype(str).str.strip().replace('', pd.NA).dropna().nunique())
    conflict_prices = data.groupby('pick_key')['decimal_price'].transform(lambda series: series.fillna('').astype(str).str.strip().replace('', pd.NA).dropna().nunique())

    data['prediction_conflict'] = conflict_predictions > 1
    data['result_conflict'] = conflict_results > 1
    data['price_conflict'] = conflict_prices > 1
    data['duplicate_type'] = 'clean'
    data.loc[data['duplicate_exact_count'] > 1, 'duplicate_type'] = 'exact_duplicate'
    data.loc[(data['duplicate_pick_count'] > 1) & (data['duplicate_exact_count'] <= 1), 'duplicate_type'] = 'same_pick_variant'
    data.loc[data['prediction_conflict'], 'duplicate_type'] = 'prediction_conflict'
    data.loc[data['result_conflict'], 'duplicate_type'] = 'result_conflict'
    data.loc[data['price_conflict'] & ~data['prediction_conflict'] & ~data['result_conflict'], 'duplicate_type'] = 'price_conflict'
    return data


def duplicate_conflict_summary(frame: pd.DataFrame) -> dict[str, int]:
    checked = build_duplicate_conflict_frame(frame)
    if checked.empty:
        return {'rows': 0, 'clean': 0, 'exact_duplicates': 0, 'same_pick_variants': 0, 'prediction_conflicts': 0, 'result_conflicts': 0, 'price_conflicts': 0}
    duplicate_type = checked['duplicate_type'].fillna('').astype(str)
    return {
        'rows': int(len(checked)),
        'clean': int(duplicate_type.eq('clean').sum()),
        'exact_duplicates': int(duplicate_type.eq('exact_duplicate').sum()),
        'same_pick_variants': int(duplicate_type.eq('same_pick_variant').sum()),
        'prediction_conflicts': int(duplicate_type.eq('prediction_conflict').sum()),
        'result_conflicts': int(duplicate_type.eq('result_conflict').sum()),
        'price_conflicts': int(duplicate_type.eq('price_conflict').sum()),
    }
