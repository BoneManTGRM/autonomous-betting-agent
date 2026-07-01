from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

import pandas as pd
import requests

from .odds_lock_tools import profit_units
from .row_normalizer import normalize_frame, safe_text

SUPPORTED_RESULT_MARKETS = {'h2h', 'moneyline', 'winner', 'match_winner'}
TEAM_SPLIT_RE = re.compile(r'\s+(?:at|vs\.?|v\.?|@)\s+', re.IGNORECASE)


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def _norm(value: Any) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', safe_text(value).lower()).strip()


def _parse_utc(value: Any) -> datetime | None:
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


def _event_parts(value: Any) -> tuple[str, str]:
    parts = [part.strip() for part in TEAM_SPLIT_RE.split(safe_text(value), maxsplit=1)]
    if len(parts) != 2:
        return '', ''
    return _norm(parts[0]), _norm(parts[1])


def fetch_the_odds_scores(*, sport_key: str, api_key: str, days_from: int = 3, timeout: int = 12) -> list[dict[str, Any]]:
    if not api_key or not sport_key:
        return []
    url = f'https://api.the-odds-api.com/v4/sports/{sport_key}/scores/'
    response = requests.get(url, params={'apiKey': api_key, 'daysFrom': int(days_from)}, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    return payload if isinstance(payload, list) else []


def _fetch_score_map(sport_keys: Iterable[str], *, api_key: str, days_from: int) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    scores: dict[str, list[dict[str, Any]]] = {}
    errors: list[str] = []
    for sport_key in sorted({safe_text(value) for value in sport_keys if safe_text(value)}):
        try:
            scores[sport_key] = fetch_the_odds_scores(sport_key=sport_key, api_key=api_key, days_from=days_from)
        except Exception as exc:
            scores[sport_key] = []
            errors.append(f'{sport_key}: {exc}')
    return scores, errors


def _score_winner(score_event: Mapping[str, Any]) -> tuple[str, str]:
    scores = score_event.get('scores') or []
    if not isinstance(scores, list) or len(scores) < 2:
        return '', ''
    parsed: list[tuple[str, int]] = []
    for item in scores:
        if isinstance(item, Mapping):
            value = _safe_float(item.get('score'))
            name = safe_text(item.get('name'))
            if name and value is not None:
                parsed.append((name, int(value)))
    if len(parsed) < 2:
        return '', ''
    final_score = f'{parsed[0][0]} {parsed[0][1]} - {parsed[1][1]} {parsed[1][0]}'
    if parsed[0][1] == parsed[1][1]:
        return 'draw/push', final_score
    return (parsed[0][0] if parsed[0][1] > parsed[1][1] else parsed[1][0]), final_score


def _match_score_event(row: Mapping[str, Any], score_events: Iterable[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    event_id = safe_text(row.get('event_id') or row.get('api_event_id'))
    row_away, row_home = _event_parts(row.get('event'))
    row_start = _parse_utc(row.get('event_start_utc'))
    for score_event in score_events:
        if not isinstance(score_event, Mapping):
            continue
        if event_id and event_id == safe_text(score_event.get('id')):
            return score_event
        away = _norm(score_event.get('away_team'))
        home = _norm(score_event.get('home_team'))
        if not away or not home or not row_away or not row_home or {away, home} != {row_away, row_home}:
            continue
        score_start = _parse_utc(score_event.get('commence_time'))
        if row_start and score_start and abs((row_start - score_start).total_seconds()) > 18 * 3600:
            continue
        return score_event
    return None


def closing_line_metrics(row: Mapping[str, Any]) -> dict[str, Any]:
    locked_price = _safe_float(row.get('decimal_price'))
    close_price = _safe_float(row.get('closing_decimal_price') or row.get('closing_price') or row.get('api_closing_decimal_price'))
    if locked_price is None or close_price is None or locked_price <= 1.0 or close_price <= 1.0:
        return {'clv_decimal_delta': None, 'clv_percent': None, 'beat_close': None}
    return {
        'clv_decimal_delta': round(locked_price - close_price, 6),
        'clv_percent': round((locked_price / close_price) - 1.0, 6),
        'beat_close': bool(locked_price > close_price),
    }


def apply_clv_columns(rows: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    frame = normalize_frame(pd.DataFrame(rows) if isinstance(rows, list) else rows)
    if frame.empty:
        return pd.DataFrame()
    out = []
    for row in frame.to_dict('records'):
        item = dict(row)
        item.update(closing_line_metrics(item))
        out.append(item)
    return pd.DataFrame(out)


def grade_moneyline_row(row: Mapping[str, Any], *, winner: str, final_score: str = '', source: str = 'api') -> dict[str, Any]:
    item = dict(row)
    market = safe_text(item.get('market_type')).lower().replace(' ', '_')
    if market and market not in SUPPORTED_RESULT_MARKETS:
        item['api_grade_status'] = 'manual_review_market_not_supported'
        return item
    pick = safe_text(item.get('prediction')).lower()
    clean_winner = safe_text(winner)
    if not pick or not clean_winner:
        item['api_grade_status'] = 'manual_review_missing_pick_or_winner'
        return item
    item['winner'] = clean_winner
    if final_score:
        item['final_score'] = final_score
    if clean_winner.lower() == 'draw/push':
        item['result_status'] = 'void'
    else:
        item['result_status'] = 'win' if pick == clean_winner.lower() else 'loss'
    item['api_grade_source'] = source
    item['api_grade_status'] = 'graded_from_api_score'
    item['profit_units'] = profit_units(item)
    item.update(closing_line_metrics(item))
    return item


def auto_full_update_rows(rows: pd.DataFrame | list[dict[str, Any]], *, odds_api_key: str | None = None, days_from: int = 3) -> tuple[pd.DataFrame, dict[str, Any]]:
    frame = apply_clv_columns(rows)
    if frame.empty:
        return pd.DataFrame(), {'input_rows': 0, 'updated_rows': 0, 'api_errors': []}
    score_map, api_errors = _fetch_score_map(frame.get('sport_key', pd.Series(dtype=str)).tolist(), api_key=odds_api_key or '', days_from=days_from) if odds_api_key else ({}, ['ODDS_API_KEY missing'])
    updated = []
    changed = 0
    protected = {'locked_at_utc', 'proof_hash', 'proof_id', 'model_probability', 'decimal_price', 'prediction'}
    for row in frame.to_dict('records'):
        before = {key: row.get(key) for key in protected}
        item = dict(row)
        score_event = _match_score_event(item, score_map.get(safe_text(item.get('sport_key')), []))
        if score_event and str(score_event.get('completed')).lower() in {'true', '1', 'yes'}:
            winner, final_score = _score_winner(score_event)
            if winner:
                item = grade_moneyline_row(item, winner=winner, final_score=final_score, source='the_odds_api_scores')
                changed += 1
        elif safe_text(item.get('api_winner')) and safe_text(item.get('result_status')).lower() in {'', 'pending', 'scheduled'}:
            item = grade_moneyline_row(item, winner=safe_text(item.get('api_winner')), final_score=safe_text(item.get('api_final_score')), source=safe_text(item.get('api_grade_source')) or 'verified_api_column')
            changed += 1
        item['api_update_protected_fields_ok'] = all(item.get(key) == before.get(key) for key in protected)
        updated.append(item)
    out = pd.DataFrame(updated)
    return out, {
        'input_rows': int(len(frame)),
        'updated_rows': int(changed),
        'api_errors': api_errors,
        'api_sports_checked': int(len(score_map)),
        'protected_fields_ok': bool(out.get('api_update_protected_fields_ok', pd.Series([True])).fillna(False).all()),
        'selection_thresholds_changed': False,
        'days_from': int(days_from),
    }


def report_quality_checks(rows: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    frame = apply_clv_columns(rows)
    if frame.empty:
        return {'pick_rows': 0, 'unique_events': 0, 'duplicate_pick_rows': 0, 'resolved_pick_rows': 0, 'pending_pick_rows': 0}
    if 'event_id' in frame.columns and frame['event_id'].astype(str).str.strip().ne('').any():
        event_key = frame['event_id'].astype(str)
    else:
        event_key = frame.get('event', pd.Series(dtype=str)).astype(str).str.lower() + '|' + frame.get('event_start_utc', pd.Series(dtype=str)).astype(str).str[:10]
    statuses = frame.get('result_status', pd.Series(dtype=str)).astype(str).str.lower()
    resolved = statuses.isin(['win', 'loss'])
    clv = pd.to_numeric(frame.get('clv_percent', pd.Series(dtype=float)), errors='coerce')
    beat = frame.get('beat_close', pd.Series(dtype=object)).dropna()
    return {
        'pick_rows': int(len(frame)),
        'unique_events': int(event_key.nunique(dropna=True)),
        'duplicate_pick_rows': int(max(0, len(frame) - event_key.nunique(dropna=True))),
        'resolved_pick_rows': int(resolved.sum()),
        'pending_pick_rows': int(statuses.eq('pending').sum()),
        'void_pick_rows': int(statuses.isin(['void', 'push']).sum()),
        'unique_event_reporting_enabled': True,
        'avg_clv_percent': None if clv.dropna().empty else round(float(clv.dropna().mean()), 6),
        'beat_close_rate': None if beat.empty else round(float(beat.astype(bool).mean()), 6),
    }


def quality_checks_frame(rows: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    checks = report_quality_checks(rows)
    return pd.DataFrame([{'check': key, 'value': value} for key, value in checks.items()])
