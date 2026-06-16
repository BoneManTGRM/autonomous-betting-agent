from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .row_normalizer import normalize_frame, probability_value, safe_text

DISPLAY_COLUMNS = [
    'event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price',
    'bookmaker', 'bookmaker_count', 'books', 'market_implied_probability', 'no_vig_implied_probability',
    'market_hold', 'fair_decimal_price', 'fair_american_price', 'edge_probability', 'edge_percent',
    'expected_value_per_unit', 'value_rating', 'odds_accuracy_score', 'odds_quality_flags',
    'manual_probability_adjustment', 'manual_context_notes', 'event_start_utc',
]


def _num(value: Any) -> float | None:
    try:
        parsed = float(str(value).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _prob_from_any(value: Any) -> float | None:
    parsed = _num(value)
    if parsed is None:
        return None
    if 1.0 < parsed <= 100.0:
        parsed /= 100.0
    if 0.0 < parsed < 1.0:
        return parsed
    return None


def _price(value: Any) -> float | None:
    parsed = _num(value)
    if parsed is None:
        return None
    if parsed >= 100:
        return 1.0 + parsed / 100.0
    if parsed <= -100:
        return 1.0 + 100.0 / abs(parsed)
    if parsed > 1.0:
        return parsed
    return None


def _american_from_probability(probability: float | None) -> str:
    if probability is None or probability <= 0.0 or probability >= 1.0:
        return ''
    if probability >= 0.5:
        return str(int(round(-100.0 * probability / (1.0 - probability))))
    return f'+{int(round(100.0 * (1.0 - probability) / probability))}'


def _parse_time(value: Any) -> datetime | None:
    text = safe_text(value)
    if not text:
        return None
    try:
        if text.endswith('Z'):
            text = text[:-1] + '+00:00'
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _book_count(row: dict[str, Any]) -> int:
    for key in ['bookmaker_count', 'books', 'source_count', 'bookmakers']:
        value = row.get(key)
        number = _num(value)
        if number is not None:
            return int(max(0, round(number)))
        text = safe_text(value)
        if ',' in text:
            return len([item for item in text.split(',') if item.strip()])
    return 0


def _field_score(row: dict[str, Any]) -> tuple[int, list[str]]:
    required = ['event', 'prediction', 'model_probability', 'decimal_price', 'event_start_utc']
    recommended = ['bookmaker', 'odds_source', 'bookmaker_count', 'closing_decimal_price', 'manual_context_notes']
    score = 0
    flags: list[str] = []
    for field in required:
        if safe_text(row.get(field)):
            score += 12
        else:
            flags.append(f'missing_{field}')
    for field in recommended:
        if safe_text(row.get(field)):
            score += 5
    return score, flags


def _value_rating(edge: float | None, ev: float | None, quality: int) -> str:
    if edge is None or ev is None:
        return 'insufficient_data'
    if quality < 55:
        return 'data_too_weak'
    if edge >= 0.075 and ev >= 0.08 and quality >= 75:
        return 'premium_value'
    if edge >= 0.04 and ev > 0:
        return 'positive_value'
    if edge >= 0.015 and ev > -0.02:
        return 'thin_value_watch'
    if edge < 0:
        return 'negative_value'
    return 'fair_or_no_edge'


def _quality_score(row: dict[str, Any], implied: float | None, probability: float | None, hold: float | None, now: datetime) -> tuple[int, str]:
    score, flags = _field_score(row)
    if probability is not None:
        score += 10
    if implied is not None:
        score += 10
    books = _book_count(row)
    if books >= 5:
        score += 10
    elif books >= 3:
        score += 7
    elif books >= 1:
        score += 3
    else:
        flags.append('missing_book_count')
    start = _parse_time(row.get('event_start_utc'))
    if start is None:
        flags.append('missing_or_invalid_event_start')
    elif start > now:
        score += 8
    else:
        flags.append('event_started_or_finished')
    if hold is not None:
        if 0.0 <= hold <= 0.09:
            score += 7
        elif hold > 0.12:
            flags.append('high_market_hold')
    price_range = _num(row.get('price_range'))
    if price_range is not None:
        if price_range <= 0.08:
            score += 5
        elif price_range >= 0.25:
            flags.append('wide_price_range')
    if safe_text(row.get('manual_context_notes')):
        score += 4
    if safe_text(row.get('closing_decimal_price')):
        score += 4
    return int(max(0, min(100, score))), '; '.join(flags)


def enrich_odds_accuracy(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if normalized.empty:
        return pd.DataFrame()
    data = normalized.copy()
    data['_group_key'] = (
        data.get('event', pd.Series(index=data.index, dtype=str)).fillna('').astype(str).str.lower().str.strip()
        + '|'
        + data.get('market_type', pd.Series(index=data.index, dtype=str)).fillna('').astype(str).str.lower().str.strip()
    )
    implied_values = []
    probabilities = []
    for row in data.to_dict(orient='records'):
        price = _price(row.get('decimal_price') or row.get('best_price') or row.get('odds'))
        implied_values.append(None if price is None else round(1.0 / price, 6))
        probabilities.append(probability_value(row, 'model_probability') or _prob_from_any(row.get('model_probability_clean')))
    data['_implied_tmp'] = implied_values
    data['_prob_tmp'] = probabilities
    group_sum = data.groupby('_group_key')['_implied_tmp'].transform(lambda values: pd.to_numeric(values, errors='coerce').sum())
    now = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(data.to_dict(orient='records')):
        item = dict(row)
        price = _price(item.get('decimal_price') or item.get('best_price') or item.get('odds'))
        probability = item.get('_prob_tmp')
        implied = item.get('_implied_tmp')
        total_implied = float(group_sum.iloc[idx]) if idx < len(group_sum) and pd.notna(group_sum.iloc[idx]) else 0.0
        no_vig = round(float(implied) / total_implied, 6) if implied is not None and total_implied > 1.0 else None
        hold = round(total_implied - 1.0, 6) if total_implied > 1.0 else None
        edge_base = no_vig if no_vig is not None else implied
        edge = round(float(probability) - float(edge_base), 6) if probability is not None and edge_base is not None else None
        ev = round(float(probability) * float(price) - 1.0, 6) if probability is not None and price is not None else None
        fair_decimal = round(1.0 / probability, 4) if probability is not None and probability > 0 else None
        quality, flags = _quality_score(item, implied, probability, hold, now)
        if price is not None:
            item['decimal_price'] = round(price, 6)
        if probability is not None:
            item['model_probability'] = round(float(probability), 6)
            item['model_probability_clean'] = round(float(probability), 6)
        item['market_implied_probability'] = implied
        item['no_vig_implied_probability'] = no_vig
        item['market_hold'] = hold
        item['fair_decimal_price'] = fair_decimal
        item['fair_american_price'] = _american_from_probability(probability)
        item['edge_probability'] = edge
        item['edge_percent'] = None if edge is None else round(edge * 100.0, 3)
        item['expected_value_per_unit'] = ev
        item['expected_value_percent'] = None if ev is None else round(ev * 100.0, 3)
        item['odds_accuracy_score'] = quality
        item['odds_quality_flags'] = flags
        item['value_rating'] = _value_rating(edge, ev, quality)
        item['book_count_normalized'] = _book_count(item)
        item.pop('_group_key', None)
        item.pop('_implied_tmp', None)
        item.pop('_prob_tmp', None)
        rows.append(item)
    return pd.DataFrame(rows)


def odds_accuracy_summary(frame: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    data = enrich_odds_accuracy(frame)
    if data.empty:
        return {
            'rows': 0,
            'avg_odds_accuracy_score': None,
            'positive_ev_rows': 0,
            'premium_value_rows': 0,
            'missing_price_rows': 0,
            'missing_probability_rows': 0,
            'future_rows': 0,
        }
    quality = pd.to_numeric(data.get('odds_accuracy_score', pd.Series(dtype=float)), errors='coerce')
    ev = pd.to_numeric(data.get('expected_value_per_unit', pd.Series(dtype=float)), errors='coerce')
    rating = data.get('value_rating', pd.Series(dtype=str)).astype(str)
    price = pd.to_numeric(data.get('decimal_price', pd.Series(dtype=float)), errors='coerce')
    probability = pd.to_numeric(data.get('model_probability', pd.Series(dtype=float)), errors='coerce')
    now = datetime.now(timezone.utc)
    future_rows = 0
    for value in data.get('event_start_utc', pd.Series(dtype=str)):
        parsed = _parse_time(value)
        if parsed is not None and parsed > now:
            future_rows += 1
    return {
        'rows': int(len(data)),
        'avg_odds_accuracy_score': None if quality.dropna().empty else round(float(quality.mean()), 2),
        'positive_ev_rows': int((ev > 0).sum()),
        'premium_value_rows': int(rating.eq('premium_value').sum()),
        'positive_value_rows': int(rating.isin(['premium_value', 'positive_value']).sum()),
        'missing_price_rows': int(price.isna().sum()),
        'missing_probability_rows': int(probability.isna().sum()),
        'future_rows': int(future_rows),
    }


def odds_accuracy_display_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in DISPLAY_COLUMNS if column in frame.columns]
