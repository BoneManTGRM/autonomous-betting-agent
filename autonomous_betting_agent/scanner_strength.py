from __future__ import annotations

from typing import Any

import pandas as pd

from .audit import parse_float


def _num(value: Any) -> float | None:
    parsed = parse_float(value)
    return parsed if parsed is not None else None


def _book_count(row: dict[str, Any]) -> int:
    value = _num(row.get('bookmaker_count', row.get('books')))
    return int(value or 0)


def _score_row(row: dict[str, Any]) -> dict[str, Any]:
    books = _book_count(row)
    best_price = _num(row.get('best_price') or row.get('decimal_price'))
    average_price = _num(row.get('average_price'))
    price_range = _num(row.get('price_range')) or 0.0
    overround = _num(row.get('market_overround'))
    score = 0.0
    reasons: list[str] = []

    if books >= 8:
        score += 30
        reasons.append('deep_book_coverage')
    elif books >= 4:
        score += 22
        reasons.append('good_book_coverage')
    elif books >= 2:
        score += 12
        reasons.append('thin_book_coverage')
    else:
        score += 3
        reasons.append('single_or_missing_book')

    if best_price and best_price > 1:
        score += 20
        reasons.append('usable_best_price')
    else:
        reasons.append('missing_best_price')

    if average_price and best_price and best_price > average_price:
        improvement = min((best_price / average_price - 1.0) * 100.0, 10.0)
        score += improvement * 2.0
        reasons.append('best_price_above_average')

    if price_range >= 0.12:
        score += 15
        reasons.append('wide_price_range')
    elif price_range >= 0.05:
        score += 8
        reasons.append('moderate_price_range')

    if overround is not None:
        if 0 < overround <= 1.06:
            score += 15
            reasons.append('efficient_market')
        elif overround <= 1.10:
            score += 8
            reasons.append('acceptable_market_hold')
        else:
            score -= 5
            reasons.append('expensive_market_hold')

    market_type = str(row.get('market_type', '')).lower()
    if market_type in {'h2h', 'spreads', 'totals'}:
        score += 5

    score = round(max(0.0, min(100.0, score)), 2)
    if score >= 75:
        tier = 'premium_scan'
        recommendation = 'send_to_what_are_the_odds'
    elif score >= 55:
        tier = 'usable_scan'
        recommendation = 'review_for_value'
    elif score >= 35:
        tier = 'thin_scan'
        recommendation = 'monitor_or_rescan'
    else:
        tier = 'weak_scan'
        recommendation = 'skip_until_more_data'

    return {
        'scanner_strength_score': score,
        'scanner_strength_tier': tier,
        'scanner_recommendation': recommendation,
        'scanner_reasons': ' | '.join(reasons),
        'scanner_book_count_clean': books,
    }


def score_scanner_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for row in frame.to_dict(orient='records'):
        item = dict(row)
        item.update(_score_row(row))
        rows.append(item)
    result = pd.DataFrame(rows)
    if 'scanner_strength_score' in result.columns:
        result = result.sort_values(['scanner_strength_score'], ascending=False)
    return result.reset_index(drop=True)


def scanner_strength_summary(frame: pd.DataFrame) -> dict[str, Any]:
    scored = score_scanner_frame(frame)
    if scored.empty:
        return {'rows': 0, 'premium_scan': 0, 'usable_scan': 0, 'thin_scan': 0, 'weak_scan': 0, 'avg_score': None}
    tiers = scored['scanner_strength_tier'].fillna('').astype(str)
    return {
        'rows': int(len(scored)),
        'premium_scan': int(tiers.eq('premium_scan').sum()),
        'usable_scan': int(tiers.eq('usable_scan').sum()),
        'thin_scan': int(tiers.eq('thin_scan').sum()),
        'weak_scan': int(tiers.eq('weak_scan').sum()),
        'avg_score': round(float(pd.to_numeric(scored['scanner_strength_score'], errors='coerce').fillna(0).mean()), 2),
    }
