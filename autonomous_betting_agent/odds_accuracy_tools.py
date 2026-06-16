from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .row_normalizer import normalize_frame, probability_value, safe_text

DISPLAY_COLUMNS = [
    'event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price',
    'bookmaker', 'bookmaker_count', 'books', 'market_implied_probability', 'no_vig_implied_probability',
    'market_hold', 'fair_decimal_price', 'fair_american_price', 'edge_probability', 'edge_percent',
    'expected_value_per_unit', 'expected_value_percent', 'price_vs_fair_percent', 'closing_decimal_price',
    'closing_value_percent', 'beat_closing_price', 'value_rating', 'odds_trust_grade', 'recommended_action',
    'odds_accuracy_score', 'odds_quality_flags', 'needed_info', 'manual_context_risk',
    'manual_probability_adjustment', 'manual_context_notes', 'event_start_utc',
]

ACTION_ORDER = {
    'lock_candidate': 1,
    'shortlist_review': 2,
    'watch_only': 3,
    'needs_more_info': 4,
    'rescan_prices': 5,
    'skip': 6,
}


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


def _manual_context_risk(row: dict[str, Any]) -> str:
    adjustment = _num(row.get('manual_probability_adjustment')) or 0.0
    confidence = _num(row.get('manual_context_confidence'))
    notes = safe_text(row.get('manual_context_notes'))
    adjustment_abs = abs(adjustment)
    if adjustment_abs > 1.0:
        adjustment_abs /= 100.0
    if adjustment_abs >= 0.05 and not notes:
        return 'large_adjustment_without_notes'
    if adjustment_abs >= 0.04 and confidence is not None and confidence < 60:
        return 'large_adjustment_low_confidence'
    if adjustment_abs >= 0.03 and not notes:
        return 'manual_notes_recommended'
    return 'ok' if adjustment_abs > 0 else ''


def _needed_info(flags: str, row: dict[str, Any]) -> str:
    needed: list[str] = []
    flag_text = safe_text(flags)
    mapping = {
        'missing_model_probability': 'model probability',
        'missing_decimal_price': 'decimal odds/current price',
        'missing_event_start': 'event start time',
        'missing_or_invalid_event_start': 'valid event start time',
        'missing_book_count': 'book count / market depth',
        'missing_bookmaker': 'bookmaker/source',
        'event_started_or_finished': 'future event only for locking',
        'high_market_hold': 'better price or lower-hold market',
        'wide_price_range': 'confirm best available price',
    }
    for key, label in mapping.items():
        if key in flag_text and label not in needed:
            needed.append(label)
    if not safe_text(row.get('manual_context_notes')) and safe_text(row.get('manual_probability_adjustment')):
        needed.append('manual adjustment notes')
    return '; '.join(needed)


def _value_rating(edge: float | None, ev: float | None, quality: int, manual_risk: str) -> str:
    if edge is None or ev is None:
        return 'insufficient_data'
    if quality < 55:
        return 'data_too_weak'
    if manual_risk and manual_risk != 'ok':
        return 'manual_review_needed'
    if edge >= 0.075 and ev >= 0.08 and quality >= 75:
        return 'premium_value'
    if edge >= 0.04 and ev > 0:
        return 'positive_value'
    if edge >= 0.015 and ev > -0.02:
        return 'thin_value_watch'
    if edge < 0 or ev < -0.02:
        return 'negative_value'
    return 'fair_or_no_edge'


def _trust_grade(quality: int, edge: float | None, ev: float | None, future: bool, manual_risk: str) -> str:
    if quality < 45 or edge is None or ev is None:
        return 'D'
    if manual_risk and manual_risk not in {'ok', ''}:
        return 'C-manual-review'
    if quality >= 85 and future and edge >= 0.075 and ev >= 0.08:
        return 'A+'
    if quality >= 75 and future and edge >= 0.04 and ev > 0:
        return 'A'
    if quality >= 65 and edge >= 0.025 and ev > -0.01:
        return 'B'
    if quality >= 55:
        return 'C'
    return 'D'


def _recommended_action(grade: str, flags: str, value_rating: str, future: bool) -> str:
    if not future:
        return 'skip'
    if grade in {'A+', 'A'} and value_rating in {'premium_value', 'positive_value'}:
        return 'lock_candidate'
    if grade == 'B' and value_rating in {'positive_value', 'thin_value_watch'}:
        return 'shortlist_review'
    if 'missing_decimal_price' in flags or 'missing_book_count' in flags or 'wide_price_range' in flags:
        return 'rescan_prices'
    if 'missing_model_probability' in flags or 'missing_or_invalid_event_start' in flags:
        return 'needs_more_info'
    if value_rating in {'negative_value', 'data_too_weak'}:
        return 'skip'
    return 'watch_only'


def _quality_score(row: dict[str, Any], implied: float | None, probability: float | None, hold: float | None, now: datetime) -> tuple[int, str, bool]:
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
    future = False
    if start is None:
        flags.append('missing_or_invalid_event_start')
    elif start > now:
        future = True
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
    manual_risk = _manual_context_risk(row)
    if manual_risk and manual_risk not in {'ok', ''}:
        flags.append(manual_risk)
        score -= 8
    return int(max(0, min(100, score))), '; '.join(sorted(set(flags))), future


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
    group_count = data.groupby('_group_key')['_implied_tmp'].transform(lambda values: pd.to_numeric(values, errors='coerce').notna().sum())
    now = datetime.now(timezone.utc)
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(data.to_dict(orient='records')):
        item = dict(row)
        price = _price(item.get('decimal_price') or item.get('best_price') or item.get('odds'))
        closing_price = _price(item.get('closing_decimal_price'))
        probability = item.get('_prob_tmp')
        implied = item.get('_implied_tmp')
        total_implied = float(group_sum.iloc[idx]) if idx < len(group_sum) and pd.notna(group_sum.iloc[idx]) else 0.0
        outcomes_in_group = int(group_count.iloc[idx]) if idx < len(group_count) and pd.notna(group_count.iloc[idx]) else 0
        no_vig = round(float(implied) / total_implied, 6) if implied is not None and total_implied > 1.0 and outcomes_in_group >= 2 else None
        hold = round(total_implied - 1.0, 6) if total_implied > 1.0 and outcomes_in_group >= 2 else None
        edge_base = no_vig if no_vig is not None else implied
        edge = round(float(probability) - float(edge_base), 6) if probability is not None and edge_base is not None else None
        ev = round(float(probability) * float(price) - 1.0, 6) if probability is not None and price is not None else None
        fair_decimal = round(1.0 / probability, 4) if probability is not None and probability > 0 else None
        price_vs_fair = round(price / fair_decimal - 1.0, 6) if price is not None and fair_decimal is not None and fair_decimal > 0 else None
        clv = round(price / closing_price - 1.0, 6) if price is not None and closing_price is not None and closing_price > 1.0 else None
        manual_risk = _manual_context_risk(item)
        quality, flags, future = _quality_score(item, implied, probability, hold, now)
        rating = _value_rating(edge, ev, quality, manual_risk)
        grade = _trust_grade(quality, edge, ev, future, manual_risk)
        action = _recommended_action(grade, flags, rating, future)
        if price is not None:
            item['decimal_price'] = round(price, 6)
        if closing_price is not None:
            item['closing_decimal_price'] = round(closing_price, 6)
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
        item['price_vs_fair_percent'] = None if price_vs_fair is None else round(price_vs_fair * 100.0, 3)
        item['closing_value_percent'] = None if clv is None else round(clv * 100.0, 3)
        item['beat_closing_price'] = None if clv is None else bool(clv > 0)
        item['odds_accuracy_score'] = quality
        item['odds_quality_flags'] = flags
        item['needed_info'] = _needed_info(flags, item)
        item['manual_context_risk'] = manual_risk
        item['value_rating'] = rating
        item['odds_trust_grade'] = grade
        item['recommended_action'] = action
        item['recommended_action_rank'] = ACTION_ORDER.get(action, 99)
        item['book_count_normalized'] = _book_count(item)
        item.pop('_group_key', None)
        item.pop('_implied_tmp', None)
        item.pop('_prob_tmp', None)
        rows.append(item)
    out = pd.DataFrame(rows)
    sort_cols = [col for col in ['recommended_action_rank', 'odds_accuracy_score', 'expected_value_per_unit', 'edge_probability'] if col in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols, ascending=[True, False, False, False]).reset_index(drop=True)
    return out


def odds_accuracy_summary(frame: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    data = enrich_odds_accuracy(frame)
    if data.empty:
        return {
            'rows': 0,
            'avg_odds_accuracy_score': None,
            'positive_ev_rows': 0,
            'premium_value_rows': 0,
            'positive_value_rows': 0,
            'lock_candidate_rows': 0,
            'shortlist_review_rows': 0,
            'needs_more_info_rows': 0,
            'rescan_price_rows': 0,
            'missing_price_rows': 0,
            'missing_probability_rows': 0,
            'future_rows': 0,
        }
    quality = pd.to_numeric(data.get('odds_accuracy_score', pd.Series(dtype=float)), errors='coerce')
    ev = pd.to_numeric(data.get('expected_value_per_unit', pd.Series(dtype=float)), errors='coerce')
    rating = data.get('value_rating', pd.Series(dtype=str)).astype(str)
    action = data.get('recommended_action', pd.Series(dtype=str)).astype(str)
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
        'lock_candidate_rows': int(action.eq('lock_candidate').sum()),
        'shortlist_review_rows': int(action.eq('shortlist_review').sum()),
        'needs_more_info_rows': int(action.eq('needs_more_info').sum()),
        'rescan_price_rows': int(action.eq('rescan_prices').sum()),
        'missing_price_rows': int(price.isna().sum()),
        'missing_probability_rows': int(probability.isna().sum()),
        'future_rows': int(future_rows),
    }


def odds_accuracy_display_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in DISPLAY_COLUMNS if column in frame.columns]
