from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .row_normalizer import normalize_frame, probability_value, safe_text

DISPLAY_COLUMNS = [
    'event', 'sport', 'market_type', 'prediction', 'model_probability', 'decimal_price',
    'best_available_price', 'best_available_book', 'line_shop_count', 'price_spread_percent',
    'bookmaker', 'bookmaker_count', 'books', 'market_implied_probability', 'no_vig_implied_probability',
    'market_hold', 'market_hold_status', 'fair_decimal_price', 'fair_american_price',
    'minimum_playable_decimal', 'great_value_decimal', 'edge_probability', 'edge_percent',
    'edge_vs_no_vig_probability', 'edge_vs_no_vig_percent', 'expected_value_per_unit',
    'expected_value_percent', 'robust_expected_value_per_unit', 'robust_expected_value_percent',
    'price_vs_fair_percent', 'closing_decimal_price', 'closing_value_percent', 'beat_closing_price',
    'price_confidence_score', 'value_rating', 'robust_value_rating', 'odds_trust_grade',
    'recommended_action', 'odds_accuracy_score', 'odds_quality_flags', 'needed_info',
    'manual_context_risk', 'manual_probability_adjustment', 'manual_context_notes', 'event_start_utc',
]

ACTION_ORDER = {
    'lock_candidate': 1,
    'shortlist_review': 2,
    'watch_only': 3,
    'needs_more_info': 4,
    'rescan_prices': 5,
    'skip': 6,
}

BOOK_PRICE_COLUMNS = {
    'DraftKings': ['draftkings_decimal_price', 'draftkings_odds', 'dk_decimal_price'],
    'FanDuel': ['fanduel_decimal_price', 'fanduel_odds', 'fd_decimal_price'],
    'Bet365': ['bet365_decimal_price', 'bet365_odds'],
    'Pinnacle': ['pinnacle_decimal_price', 'pinnacle_odds'],
    'Caesars': ['caesars_decimal_price', 'caesars_odds'],
    'MGM': ['mgm_decimal_price', 'betmgm_decimal_price', 'mgm_odds', 'betmgm_odds'],
    'Local/Other': ['local_decimal_price', 'local_odds', 'other_decimal_price', 'other_odds'],
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


def _available_prices(row: dict[str, Any]) -> list[dict[str, Any]]:
    prices: list[dict[str, Any]] = []
    seen: set[tuple[str, float]] = set()

    def add(book: str, value: Any, source_column: str) -> None:
        price = _price(value)
        if price is None:
            return
        key = (book.lower().strip(), round(price, 6))
        if key in seen:
            return
        seen.add(key)
        prices.append({'bookmaker': book or 'Unknown', 'decimal_price': round(price, 6), 'source_column': source_column})

    base_book = safe_text(row.get('bookmaker') or row.get('odds_source')) or 'Entered price'
    add(base_book, row.get('decimal_price'), 'decimal_price')
    add(base_book, row.get('best_price'), 'best_price')
    add(base_book, row.get('odds'), 'odds')
    for bookmaker, columns in BOOK_PRICE_COLUMNS.items():
        for column in columns:
            if safe_text(row.get(column)):
                add(bookmaker, row.get(column), column)
                break
    return prices


def _price_summary(row: dict[str, Any]) -> dict[str, Any]:
    prices = _available_prices(row)
    if not prices:
        return {
            'best_available_price': None,
            'best_available_book': '',
            'worst_available_price': None,
            'average_available_price': None,
            'line_shop_count': 0,
            'price_spread_percent': None,
            'price_source_column': '',
        }
    values = [float(item['decimal_price']) for item in prices]
    best = max(prices, key=lambda item: float(item['decimal_price']))
    worst = min(values)
    best_value = float(best['decimal_price'])
    spread = round(((best_value / worst) - 1.0) * 100.0, 3) if worst > 0 else None
    return {
        'best_available_price': round(best_value, 6),
        'best_available_book': safe_text(best.get('bookmaker')),
        'worst_available_price': round(worst, 6),
        'average_available_price': round(sum(values) / len(values), 6),
        'line_shop_count': int(len(prices)),
        'price_spread_percent': spread,
        'price_source_column': safe_text(best.get('source_column')),
    }


def _market_hold_status(hold: float | None) -> str:
    if hold is None:
        return 'unknown_hold'
    if hold <= 0.04:
        return 'efficient_low_hold'
    if hold <= 0.09:
        return 'normal_hold'
    if hold <= 0.12:
        return 'elevated_hold'
    return 'high_hold'


def _minimum_playable(probability: float | None, min_edge: float = 0.03, great_edge: float = 0.075) -> dict[str, Any]:
    if probability is None or not (0.0 < probability < 1.0):
        return {'minimum_playable_decimal': None, 'great_value_decimal': None}
    return {
        'minimum_playable_decimal': round(1.0 / max(0.01, probability - min_edge), 4),
        'great_value_decimal': round(1.0 / max(0.01, probability - great_edge), 4),
    }


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
        'single_book_price': 'compare at least 2-3 books',
        'missing_bookmaker': 'bookmaker/source',
        'event_started_or_finished': 'future event only for locking',
        'high_market_hold': 'better price or lower-hold market',
        'very_high_market_hold': 'avoid high-vig market unless edge is exceptional',
        'wide_price_range': 'confirm best available price',
        'price_below_fair': 'better odds before playing',
        'thin_edge_after_haircut': 'larger margin of safety',
    }
    for key, label in mapping.items():
        if key in flag_text and label not in needed:
            needed.append(label)
    if not safe_text(row.get('manual_context_notes')) and safe_text(row.get('manual_probability_adjustment')):
        needed.append('manual adjustment notes')
    return '; '.join(needed)


def _value_rating(edge: float | None, ev: float | None, robust_ev: float | None, quality: int, manual_risk: str) -> str:
    if edge is None or ev is None:
        return 'insufficient_data'
    if quality < 55:
        return 'data_too_weak'
    if manual_risk and manual_risk != 'ok':
        return 'manual_review_needed'
    if edge >= 0.075 and ev >= 0.08 and robust_ev is not None and robust_ev > 0.03 and quality >= 75:
        return 'premium_value'
    if edge >= 0.04 and ev > 0 and (robust_ev is None or robust_ev > -0.01):
        return 'positive_value'
    if edge >= 0.015 and ev > -0.02:
        return 'thin_value_watch'
    if edge < 0 or ev < -0.02:
        return 'negative_value'
    return 'fair_or_no_edge'


def _robust_rating(robust_ev: float | None, robust_edge: float | None) -> str:
    if robust_ev is None or robust_edge is None:
        return 'unknown_robust_value'
    if robust_ev >= 0.06 and robust_edge >= 0.04:
        return 'robust_positive_value'
    if robust_ev > 0 and robust_edge > 0:
        return 'slightly_positive_after_haircut'
    if robust_ev > -0.02:
        return 'thin_or_uncertain_after_haircut'
    return 'negative_after_haircut'


def _trust_grade(quality: int, edge: float | None, ev: float | None, robust_ev: float | None, future: bool, manual_risk: str) -> str:
    if quality < 45 or edge is None or ev is None:
        return 'D'
    if manual_risk and manual_risk not in {'ok', ''}:
        return 'C-manual-review'
    if quality >= 85 and future and edge >= 0.075 and ev >= 0.08 and robust_ev is not None and robust_ev > 0.03:
        return 'A+'
    if quality >= 75 and future and edge >= 0.04 and ev > 0 and (robust_ev is None or robust_ev > -0.005):
        return 'A'
    if quality >= 65 and edge >= 0.025 and ev > -0.01:
        return 'B'
    if quality >= 55:
        return 'C'
    return 'D'


def _recommended_action(grade: str, flags: str, value_rating: str, robust_value_rating: str, future: bool) -> str:
    if not future:
        return 'skip'
    if grade in {'A+', 'A'} and value_rating in {'premium_value', 'positive_value'} and robust_value_rating in {'robust_positive_value', 'slightly_positive_after_haircut'}:
        return 'lock_candidate'
    if grade in {'A', 'B'} and value_rating in {'positive_value', 'thin_value_watch'}:
        return 'shortlist_review'
    if 'missing_decimal_price' in flags or 'missing_book_count' in flags or 'wide_price_range' in flags or 'single_book_price' in flags:
        return 'rescan_prices'
    if 'missing_model_probability' in flags or 'missing_or_invalid_event_start' in flags:
        return 'needs_more_info'
    if value_rating in {'negative_value', 'data_too_weak'} or robust_value_rating == 'negative_after_haircut':
        return 'skip'
    return 'watch_only'


def _quality_score(row: dict[str, Any], implied: float | None, probability: float | None, hold: float | None, now: datetime) -> tuple[int, str, bool, int]:
    score, flags = _field_score(row)
    if probability is not None:
        score += 10
    if implied is not None:
        score += 10
    books = _book_count(row)
    line_shop_count = int(_num(row.get('line_shop_count')) or 0)
    price_spread = _num(row.get('price_spread_percent'))
    if books >= 5 or line_shop_count >= 5:
        score += 12
    elif books >= 3 or line_shop_count >= 3:
        score += 8
    elif books >= 1 or line_shop_count >= 1:
        score += 3
        flags.append('single_book_price')
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
        if 0.0 <= hold <= 0.04:
            score += 9
        elif hold <= 0.09:
            score += 7
        elif hold > 0.16:
            flags.append('very_high_market_hold')
            score -= 8
        elif hold > 0.12:
            flags.append('high_market_hold')
            score -= 4
    if price_spread is not None:
        if price_spread <= 5.0:
            score += 5
        elif price_spread >= 18.0:
            flags.append('wide_price_range')
            score -= 3
    if safe_text(row.get('manual_context_notes')):
        score += 4
    if safe_text(row.get('closing_decimal_price')):
        score += 4
    manual_risk = _manual_context_risk(row)
    if manual_risk and manual_risk not in {'ok', ''}:
        flags.append(manual_risk)
        score -= 8
    price_confidence = int(max(0, min(100, 55 + min(line_shop_count, 5) * 8 - (10 if price_spread and price_spread >= 18.0 else 0) - (10 if hold and hold > 0.12 else 0))))
    return int(max(0, min(100, score))), '; '.join(sorted(set(flags))), future, price_confidence


def _robust_haircut(quality: int, hold: float | None, flags: str) -> float:
    haircut = max(0.0, (100 - quality) / 100.0 * 0.035)
    if hold is not None and hold > 0.12:
        haircut += 0.015
    if 'single_book_price' in flags:
        haircut += 0.01
    if 'wide_price_range' in flags:
        haircut += 0.015
    if 'manual' in flags:
        haircut += 0.015
    return round(haircut, 6)


def enrich_odds_accuracy(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if normalized.empty:
        return pd.DataFrame()
    data = normalized.copy()
    price_summaries = []
    chosen_prices = []
    for row in data.to_dict(orient='records'):
        summary = _price_summary(row)
        price_summaries.append(summary)
        chosen_prices.append(summary.get('best_available_price') or _price(row.get('decimal_price') or row.get('best_price') or row.get('odds')))
    for key in ['best_available_price', 'best_available_book', 'worst_available_price', 'average_available_price', 'line_shop_count', 'price_spread_percent', 'price_source_column']:
        data[key] = [summary.get(key) for summary in price_summaries]
    data['_chosen_price_tmp'] = chosen_prices
    data['_group_key'] = (
        data.get('event', pd.Series(index=data.index, dtype=str)).fillna('').astype(str).str.lower().str.strip()
        + '|'
        + data.get('market_type', pd.Series(index=data.index, dtype=str)).fillna('').astype(str).str.lower().str.strip()
    )
    implied_values = []
    probabilities = []
    for row in data.to_dict(orient='records'):
        price = _price(row.get('_chosen_price_tmp'))
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
        price = _price(item.get('_chosen_price_tmp'))
        closing_price = _price(item.get('closing_decimal_price'))
        probability = item.get('_prob_tmp')
        implied = item.get('_implied_tmp')
        total_implied = float(group_sum.iloc[idx]) if idx < len(group_sum) and pd.notna(group_sum.iloc[idx]) else 0.0
        outcomes_in_group = int(group_count.iloc[idx]) if idx < len(group_count) and pd.notna(group_count.iloc[idx]) else 0
        no_vig = round(float(implied) / total_implied, 6) if implied is not None and total_implied > 1.0 and outcomes_in_group >= 2 else None
        hold = round(total_implied - 1.0, 6) if total_implied > 1.0 and outcomes_in_group >= 2 else None
        edge_base = no_vig if no_vig is not None else implied
        edge = round(float(probability) - float(edge_base), 6) if probability is not None and edge_base is not None else None
        raw_edge = round(float(probability) - float(implied), 6) if probability is not None and implied is not None else None
        ev = round(float(probability) * float(price) - 1.0, 6) if probability is not None and price is not None else None
        fair_decimal = round(1.0 / probability, 4) if probability is not None and probability > 0 else None
        minimums = _minimum_playable(probability)
        price_vs_fair = round(price / fair_decimal - 1.0, 6) if price is not None and fair_decimal is not None and fair_decimal > 0 else None
        clv = round(price / closing_price - 1.0, 6) if price is not None and closing_price is not None and closing_price > 1.0 else None
        manual_risk = _manual_context_risk(item)
        quality, flags, future, price_confidence = _quality_score(item, implied, probability, hold, now)
        haircut = _robust_haircut(quality, hold, flags)
        robust_edge = None if edge is None else round(edge - haircut, 6)
        robust_ev = None if ev is None else round(ev - haircut, 6)
        if price_vs_fair is not None and price_vs_fair < 0:
            flags = '; '.join(sorted(set([flag for flag in flags.split('; ') if flag] + ['price_below_fair'])))
        if robust_ev is not None and robust_ev <= 0 and ev is not None and ev > 0:
            flags = '; '.join(sorted(set([flag for flag in flags.split('; ') if flag] + ['thin_edge_after_haircut'])))
        rating = _value_rating(edge, ev, robust_ev, quality, manual_risk)
        robust_rating = _robust_rating(robust_ev, robust_edge)
        grade = _trust_grade(quality, edge, ev, robust_ev, future, manual_risk)
        action = _recommended_action(grade, flags, rating, robust_rating, future)
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
        item['market_hold_status'] = _market_hold_status(hold)
        item['fair_decimal_price'] = fair_decimal
        item['fair_american_price'] = _american_from_probability(probability)
        item['minimum_playable_decimal'] = minimums['minimum_playable_decimal']
        item['great_value_decimal'] = minimums['great_value_decimal']
        item['edge_probability'] = edge
        item['edge_percent'] = None if edge is None else round(edge * 100.0, 3)
        item['edge_vs_no_vig_probability'] = edge
        item['edge_vs_no_vig_percent'] = None if edge is None else round(edge * 100.0, 3)
        item['raw_market_edge_probability'] = raw_edge
        item['raw_market_edge_percent'] = None if raw_edge is None else round(raw_edge * 100.0, 3)
        item['expected_value_per_unit'] = ev
        item['expected_value_percent'] = None if ev is None else round(ev * 100.0, 3)
        item['robust_expected_value_per_unit'] = robust_ev
        item['robust_expected_value_percent'] = None if robust_ev is None else round(robust_ev * 100.0, 3)
        item['robust_edge_probability'] = robust_edge
        item['robust_edge_percent'] = None if robust_edge is None else round(robust_edge * 100.0, 3)
        item['robust_haircut_probability'] = haircut
        item['price_vs_fair_percent'] = None if price_vs_fair is None else round(price_vs_fair * 100.0, 3)
        item['closing_value_percent'] = None if clv is None else round(clv * 100.0, 3)
        item['beat_closing_price'] = None if clv is None else bool(clv > 0)
        item['price_confidence_score'] = price_confidence
        item['odds_accuracy_score'] = quality
        item['odds_quality_flags'] = flags
        item['needed_info'] = _needed_info(flags, item)
        item['manual_context_risk'] = manual_risk
        item['value_rating'] = rating
        item['robust_value_rating'] = robust_rating
        item['odds_trust_grade'] = grade
        item['recommended_action'] = action
        item['recommended_action_rank'] = ACTION_ORDER.get(action, 99)
        item['book_count_normalized'] = max(_book_count(item), int(_num(item.get('line_shop_count')) or 0))
        item.pop('_group_key', None)
        item.pop('_implied_tmp', None)
        item.pop('_prob_tmp', None)
        item.pop('_chosen_price_tmp', None)
        rows.append(item)
    out = pd.DataFrame(rows)
    sort_cols = [col for col in ['recommended_action_rank', 'odds_accuracy_score', 'robust_expected_value_per_unit', 'expected_value_per_unit', 'edge_probability'] if col in out.columns]
    if sort_cols:
        out = out.sort_values(sort_cols, ascending=[True, False, False, False, False]).reset_index(drop=True)
    return out


def odds_accuracy_summary(frame: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    data = enrich_odds_accuracy(frame)
    if data.empty:
        return {
            'rows': 0,
            'avg_odds_accuracy_score': None,
            'positive_ev_rows': 0,
            'robust_positive_ev_rows': 0,
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
    robust_ev = pd.to_numeric(data.get('robust_expected_value_per_unit', pd.Series(dtype=float)), errors='coerce')
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
        'robust_positive_ev_rows': int((robust_ev > 0).sum()),
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
