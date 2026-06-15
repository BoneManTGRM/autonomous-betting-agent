from __future__ import annotations

import csv
import io
import json
import math
from datetime import datetime, timezone
from typing import Any

from .learning import GradedPrediction, ProbabilityCalibrator

PROBABILITY_COLUMNS = (
    'final_probability_value',
    'calibrated_probability',
    'model_probability',
    'predicted_probability',
    'pick_probability',
    'favorite_probability',
    'market_probability_value',
    'market_probability',
    'no_vig_probability',
    'confidence_probability',
    'probability',
)
RESULT_COLUMNS = ('result', 'outcome', 'win_loss', 'graded_result', 'status')
PRICE_COLUMNS = ('best_price', 'sportsbook_odds', 'decimal_odds', 'average_price', 'avg_price', 'odds', 'price')
PICK_COLUMNS = ('prediction', 'pick', 'predicted_side', 'predicted_winner', 'favorite')
WINNER_COLUMNS = ('winner', 'actual_winner', 'winning_side', 'final_winner')
EVENT_COLUMNS = ('event', 'event_name', 'game', 'match', 'fixture')
SPORT_COLUMNS = ('sport', 'sport_title', 'league', 'competition')
START_COLUMNS = ('start', 'known_start_utc', 'commence_time', 'event_date', 'date')
CONFIDENCE_COLUMNS = ('confidence', 'confidence_bucket', 'read', 'decision', 'confidence_tier')


def clean_key(value: Any) -> str:
    return str(value or '').strip().lower().replace(' ', '_').replace('-', '_')


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace('%', '').replace(',', '')
    if not text or text.lower() in {'none', 'null', 'nan', 'unknown', 'n/a', 'na', 'pending'}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_probability(value: Any) -> float | None:
    number = parse_float(value)
    if number is None:
        return None
    if 1.0 < number <= 100.0:
        number /= 100.0
    if 0.0 < number < 1.0:
        return max(0.000001, min(0.999999, number))
    return None


def parse_result(value: Any) -> int | None:
    text = '' if value is None else str(value).strip().lower()
    if text in {'won', 'win', 'w', 'correct', 'hit', 'true', 'yes', '1'}:
        return 1
    if text in {'lost', 'loss', 'l', 'incorrect', 'miss', 'false', 'no', '0'}:
        return 0
    return None


def first_text(row: dict[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = row.get(clean_key(name))
        if value not in (None, ''):
            return str(value).strip()
    return ''


def first_float(row: dict[str, Any], names: tuple[str, ...]) -> float | None:
    for name in names:
        value = parse_float(row.get(clean_key(name)))
        if value is not None:
            return value
    return None


def fallback_probability(row: dict[str, Any], source: str = '') -> tuple[float | None, str]:
    text = ' '.join([source, first_text(row, CONFIDENCE_COLUMNS), first_text(row, ('source', 'note', 'result_note'))]).lower()
    if any(token in text for token in ('a+ high', 'high confidence', 'strong_candidate', 'strong candidate')):
        return 0.70, 'fallback_high_confidence'
    if any(token in text for token in ('high', 'alta', 'a strong')):
        return 0.67, 'fallback_high_confidence'
    if any(token in text for token in ('medium', 'media', 'lean', 'b lean')):
        return 0.60, 'fallback_medium_confidence'
    if any(token in text for token in ('low', 'baja', 'watch_only', 'watch only')):
        return 0.52, 'fallback_low_confidence'
    return None, 'missing'


def extract_probability(row: dict[str, Any], source: str = '') -> tuple[float | None, str]:
    for name in PROBABILITY_COLUMNS:
        value = parse_probability(row.get(clean_key(name)))
        if value is not None:
            return value, clean_key(name)
    price = first_float(row, PRICE_COLUMNS)
    if price is not None and price > 1.0:
        return max(0.000001, min(0.999999, 1.0 / price)), 'price_implied'
    return fallback_probability(row, source)


def extract_result(row: dict[str, Any]) -> int | None:
    for name in RESULT_COLUMNS:
        value = parse_result(row.get(clean_key(name)))
        if value is not None:
            return value
    pick = first_text(row, PICK_COLUMNS).lower()
    winner = first_text(row, WINNER_COLUMNS).lower()
    if pick and winner:
        return 1 if pick == winner else 0
    return None


def compact_row(row: dict[str, Any], row_number: int, source: str) -> dict[str, Any] | None:
    probability, probability_source = extract_probability(row, source)
    result = extract_result(row)
    if probability is None or result is None:
        return None
    event = first_text(row, EVENT_COLUMNS) or f'row {row_number}'
    prediction = first_text(row, PICK_COLUMNS)
    start = first_text(row, START_COLUMNS)
    sport = first_text(row, SPORT_COLUMNS)
    price = first_float(row, PRICE_COLUMNS)
    books = first_float(row, ('books', 'bookmaker_count', 'source_count', 'bookmakers'))
    api_coverage = first_float(row, ('api_coverage_score', 'api_coverage'))
    if api_coverage is not None and api_coverage > 1.0:
        api_coverage /= 100.0
    item = {
        'event': event[:140],
        'start': start[:40],
        'sport': sport[:80],
        'prediction': prediction[:100],
        'probability': round(probability, 6),
        'probability_source': probability_source,
        'outcome': int(result),
        'best_price': None if price is None else round(float(price), 4),
        'books': None if books is None else int(max(0, round(float(books)))),
        'api_coverage_score': None if api_coverage is None else round(max(0.0, min(1.0, float(api_coverage))), 6),
        'confidence': first_text(row, CONFIDENCE_COLUMNS)[:60],
        'source': source[:120],
    }
    item['error_abs'] = round(abs(item['probability'] - item['outcome']), 6)
    item['dedupe_key'] = '|'.join(part for part in (event.lower().strip(), start[:10].lower().strip(), prediction.lower().strip(), str(result)) if part)
    return item


def read_compact_csv_bytes(data: bytes, source: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    stats = {
        'input_rows': 0,
        'usable_rows': 0,
        'missing_probability': 0,
        'missing_result': 0,
        'fallback_probability_rows': 0,
        'wins': 0,
        'losses': 0,
    }
    text = data.decode('utf-8-sig', errors='replace')
    rows: list[dict[str, Any]] = []
    for row_number, raw in enumerate(csv.DictReader(io.StringIO(text)), start=2):
        stats['input_rows'] += 1
        row = {clean_key(k): v for k, v in raw.items() if k is not None}
        probability, probability_source = extract_probability(row, source)
        result = extract_result(row)
        if probability is None:
            stats['missing_probability'] += 1
        if result is None:
            stats['missing_result'] += 1
            continue
        if probability is None:
            continue
        item = compact_row(row, row_number, source)
        if item is None:
            continue
        if str(probability_source).startswith('fallback_'):
            stats['fallback_probability_rows'] += 1
        stats['usable_rows'] += 1
        stats['wins'] += int(item['outcome'] == 1)
        stats['losses'] += int(item['outcome'] == 0)
        rows.append(item)
    return rows, stats


def valid_bank_row(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    probability = parse_probability(row.get('probability'))
    result = parse_result(row.get('outcome'))
    if probability is None or result is None:
        return None
    clean = dict(row)
    clean['probability'] = round(probability, 6)
    clean['outcome'] = int(result)
    clean['error_abs'] = round(abs(clean['probability'] - clean['outcome']), 6)
    clean['dedupe_key'] = str(clean.get('dedupe_key') or f"{clean.get('event','')}|{clean.get('start','')}|{clean.get('prediction','')}|{clean.get('outcome','')}").lower()
    return clean


def merge_dedupe_rows(existing: list[dict[str, Any]], uploaded: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: dict[str, dict[str, Any]] = {}
    duplicates = 0
    for raw in [*existing, *uploaded]:
        row = valid_bank_row(raw)
        if row is None:
            continue
        key = row['dedupe_key']
        if key in seen:
            duplicates += 1
            if sum(value not in (None, '') for value in row.values()) > sum(value not in (None, '') for value in seen[key].values()):
                seen[key] = row
        else:
            seen[key] = row
    return list(seen.values()), duplicates


def prune_rows(rows: list[dict[str, Any]], max_rows: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(rows) <= max_rows:
        return rows, {'strategy': 'no_pruning_needed', 'rows_before': len(rows), 'rows_after': len(rows), 'rows_pruned': 0}
    ordered = sorted(rows, key=lambda row: (str(row.get('start') or ''), float(row.get('error_abs') or 0.0)), reverse=True)
    recent_keep = int(max_rows * 0.75)
    recent = ordered[:recent_keep]
    recent_keys = {row['dedupe_key'] for row in recent}
    high_error = sorted([row for row in ordered if row['dedupe_key'] not in recent_keys], key=lambda row: float(row.get('error_abs') or 0.0), reverse=True)
    kept = {row['dedupe_key']: row for row in [*recent, *high_error[: max_rows - len(recent)]]}
    return list(kept.values()), {'strategy': 'kept_recent_plus_high_error', 'rows_before': len(rows), 'rows_after': len(kept), 'rows_pruned': len(rows) - len(kept)}


def probability_bucket(probability: float) -> str:
    if probability < 0.40:
        return '0-40%'
    if probability < 0.50:
        return '40-50%'
    if probability < 0.60:
        return '50-60%'
    if probability < 0.70:
        return '60-70%'
    if probability < 0.80:
        return '70-80%'
    if probability < 0.90:
        return '80-90%'
    return '90-100%'


def books_bucket(value: Any) -> str:
    number = parse_float(value)
    if number is None:
        return 'unknown'
    if number <= 1:
        return '0-1'
    if number <= 3:
        return '2-3'
    if number <= 6:
        return '4-6'
    if number <= 10:
        return '7-10'
    return '11+'


def api_bucket(value: Any) -> str:
    number = parse_float(value)
    if number is None:
        return 'unknown'
    number = max(0.0, min(1.0, number))
    if number >= 0.999:
        return '100%'
    if number >= 0.66:
        return '66-99%'
    if number >= 0.33:
        return '33-65%'
    if number > 0:
        return '1-32%'
    return '0%'


def segment_keys(row: dict[str, Any]) -> list[tuple[str, str, str]]:
    keys: list[tuple[str, str, str]] = []
    sport = str(row.get('sport') or '').strip()
    confidence = str(row.get('confidence') or '').strip()
    probability = float(row['probability'])
    bucket = probability_bucket(probability)
    keys.append(('probability_bucket', bucket, f'Probability bucket: {bucket}'))
    probability_source = str(row.get('probability_source') or '').strip()
    if probability_source:
        keys.append(('probability_source', probability_source, f'Probability source: {probability_source}'))
    if sport:
        keys.append(('sport', sport, f'Sport: {sport}'))
        keys.append(('sport_probability_bucket', f'{sport}|{bucket}', f'{sport} / {bucket}'))
    if confidence:
        keys.append(('confidence', confidence, f'Confidence/read: {confidence}'))
    if row.get('books') is not None:
        bucket_books = books_bucket(row.get('books'))
        keys.append(('books_bucket', bucket_books, f'Books: {bucket_books}'))
    if row.get('api_coverage_score') is not None:
        bucket_api = api_bucket(row.get('api_coverage_score'))
        keys.append(('api_coverage_bucket', bucket_api, f'API coverage: {bucket_api}'))
    return keys


def build_segments(rows: list[dict[str, Any]], min_records: int, max_segments: int) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        for area_type, group_value, label in segment_keys(row):
            key = f'{area_type}:{group_value}'.lower()
            grouped.setdefault(key, {'area_type': area_type, 'group_value': group_value, 'area': label, 'rows': []})['rows'].append(row)
    segments: list[dict[str, Any]] = []
    for item in grouped.values():
        group = item.pop('rows')
        records = len(group)
        if records < min_records:
            continue
        probabilities = [float(row['probability']) for row in group]
        outcomes = [int(row['outcome']) for row in group]
        avg_predicted = sum(probabilities) / records
        actual_hit_rate = sum(outcomes) / records
        smoothed_hit_rate = (sum(outcomes) + avg_predicted * 8) / (records + 8)
        smoothed_edge = smoothed_hit_rate - avg_predicted
        brier = sum((p - y) ** 2 for p, y in zip(probabilities, outcomes)) / records
        sample_weight = min(1.0, math.log(records + 1) / math.log(51))
        reliability = max(0.05, min(1.0, 0.65 * sample_weight + 0.35 * (1.0 - min(0.40, brier) / 0.40)))
        importance = abs(smoothed_edge) * sample_weight * (1.0 + min(1.0, records / 30.0))
        segments.append({
            **item,
            'records': records,
            'avg_predicted': round(avg_predicted, 6),
            'actual_hit_rate': round(actual_hit_rate, 6),
            'actual_minus_predicted': round(actual_hit_rate - avg_predicted, 6),
            'smoothed_hit_rate': round(smoothed_hit_rate, 6),
            'smoothed_edge': round(smoothed_edge, 6),
            'reliability': round(reliability, 6),
            'brier': round(brier, 6),
            'memory_type': item['area_type'],
            'importance': round(importance, 6),
            'action': 'lower_trust' if smoothed_edge < -0.035 else 'raise_trust' if smoothed_edge > 0.035 else 'watch',
        })
    segments.sort(key=lambda row: (float(row['importance']), int(row['records'])), reverse=True)
    return segments[:max_segments]


def make_ara_memory_csv(segments: list[dict[str, Any]]) -> str:
    fields = ['area', 'area_type', 'group_value', 'records', 'avg_predicted', 'actual_hit_rate', 'actual_minus_predicted', 'smoothed_hit_rate', 'smoothed_edge', 'reliability', 'brier', 'memory_type', 'importance', 'action']
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator='\n')
    writer.writeheader()
    for segment in segments:
        writer.writerow({field: segment.get(field, '') for field in fields})
    return buffer.getvalue()


def rows_to_graded(rows: list[dict[str, Any]]) -> list[GradedPrediction]:
    return [GradedPrediction(event_name=str(row.get('event') or ''), probability=float(row['probability']), outcome=int(row['outcome']), predicted_side=str(row.get('prediction') or '')) for row in rows]


def calibrator_json(calibrator: ProbabilityCalibrator) -> str:
    return json.dumps(calibrator.to_dict(), indent=2, sort_keys=True) + '\n'


def memory_metrics(rows: list[dict[str, Any]]) -> dict[str, float | int | None]:
    if not rows:
        return {'resolved': 0, 'hit_rate': None, 'avg_predicted': None, 'brier': None, 'wins': 0, 'losses': 0}
    probabilities = [float(row['probability']) for row in rows]
    outcomes = [int(row['outcome']) for row in rows]
    wins = sum(outcomes)
    return {
        'resolved': len(rows),
        'hit_rate': wins / len(rows),
        'avg_predicted': sum(probabilities) / len(rows),
        'brier': sum((p - y) ** 2 for p, y in zip(probabilities, outcomes)) / len(rows),
        'wins': wins,
        'losses': len(rows) - wins,
    }


def build_memory_bank(*, compact_rows: list[dict[str, Any]], calibrator: ProbabilityCalibrator, segments: list[dict[str, Any]], parse_stats: dict[str, Any], prune_report: dict[str, Any], mode: str, existing_count: int, uploaded_count: int, duplicates_removed: int) -> dict[str, Any]:
    return {
        'version': 'learning-memory-bank-v3',
        'trained_at_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'training_mode': mode,
        'summary': {
            'existing_rows_before_upload': existing_count,
            'uploaded_usable_rows': uploaded_count,
            'duplicates_removed': duplicates_removed,
            'rows_after_pruning': len(compact_rows),
            'patterns_saved': len(segments),
            'fallback_probability_rows': int(parse_stats.get('fallback_probability_rows', 0)),
        },
        'parse_stats': parse_stats,
        'prune_report': prune_report,
        'global_calibrator': calibrator.to_dict(),
        'patterns': segments,
        'compact_rows': compact_rows,
    }
