from __future__ import annotations

from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Mapping

import pandas as pd

from .commercial_platform_tools import filter_locked_proof_rows
from .live_odds import fetch_odds, summarize_event
from .row_normalizer import safe_text


def _now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _clean(value: Any) -> str:
    return ' '.join(safe_text(value).lower().replace('-', ' ').replace('_', ' ').replace('@', ' at ').split())


def _similarity(left: Any, right: Any) -> float:
    a, b = _clean(left), _clean(right)
    if not a or not b:
        return 0.0
    if a == b or a in b or b in a:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def _date_prefix(value: Any) -> str:
    text = safe_text(value)
    return text[:10] if len(text) >= 10 else ''


def _event_name(summary: Any) -> str:
    away = safe_text(getattr(summary, 'away_team', ''))
    home = safe_text(getattr(summary, 'home_team', ''))
    return f'{away} at {home}' if away and home else safe_text(getattr(summary, 'event_id', ''))


def _market_alias(value: Any) -> str:
    text = _clean(value)
    if text in {'moneyline', 'ml', 'h2h', 'winner'}:
        return 'h2h'
    if 'spread' in text or 'handicap' in text:
        return 'spreads'
    if 'total' in text or 'over' in text or 'under' in text:
        return 'totals'
    return text


def _pick_match_score(ledger_row: Mapping[str, Any], outcome: Any) -> float:
    prediction = _clean(ledger_row.get('prediction'))
    outcome_name = _clean(getattr(outcome, 'name', ''))
    if not prediction or not outcome_name:
        return 0.0
    score = _similarity(prediction, outcome_name)
    if outcome_name in prediction or prediction in outcome_name:
        score = max(score, 1.0)
    market = _market_alias(ledger_row.get('market_type'))
    outcome_market = _market_alias(getattr(outcome, 'market', ''))
    if market and outcome_market and market != outcome_market:
        score *= 0.35
    return score


def _best_event_match(ledger_row: Mapping[str, Any], summaries: list[Any]) -> tuple[Any | None, float]:
    best = None
    best_score = 0.0
    ledger_date = _date_prefix(ledger_row.get('event_start_utc'))
    for summary in summaries:
        event_score = _similarity(ledger_row.get('event'), _event_name(summary))
        sport_score = max(_similarity(ledger_row.get('sport_key'), getattr(summary, 'sport_key', '')), _similarity(ledger_row.get('sport'), getattr(summary, 'sport_title', '')))
        date_score = 1.0 if ledger_date and ledger_date == _date_prefix(getattr(summary, 'commence_time', '')) else 0.0
        score = event_score * 0.70 + sport_score * 0.15 + date_score * 0.15
        if score > best_score:
            best_score = score
            best = summary
    return best, best_score


def collect_closing_lines(
    ledger: pd.DataFrame | list[dict[str, Any]],
    *,
    api_key: str,
    sport_key: str,
    regions: str = 'us,eu,uk',
    markets: str = 'h2h,spreads,totals',
    event_threshold: float = 0.82,
    pick_threshold: float = 0.70,
    overwrite_existing: bool = False,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    locked = filter_locked_proof_rows(ledger)
    if locked.empty:
        return pd.DataFrame(), {'updated_rows': 0, 'checked_rows': 0, 'matched_events': 0, 'matched_picks': 0, 'reason': 'empty_ledger'}

    odds_payload = fetch_odds(api_key, sport_key=sport_key, regions=regions, markets=markets)
    summaries = [summary for event in odds_payload for summary in [summarize_event(event)] if summary is not None]
    if not summaries:
        return locked, {'updated_rows': 0, 'checked_rows': int(len(locked)), 'matched_events': 0, 'matched_picks': 0, 'reason': 'no_current_odds'}

    rows: list[dict[str, Any]] = []
    updated = 0
    matched_events = 0
    matched_picks = 0
    collected_at = _now_utc()
    wanted_sport = _clean(sport_key)

    for row in locked.to_dict(orient='records'):
        item = dict(row)
        if safe_text(item.get('closing_decimal_price')) and not overwrite_existing:
            rows.append(item)
            continue
        row_sport = _clean(item.get('sport_key') or item.get('sport'))
        if wanted_sport and row_sport and wanted_sport not in row_sport and row_sport not in wanted_sport:
            rows.append(item)
            continue
        summary, event_score = _best_event_match(item, summaries)
        if summary is None or event_score < event_threshold:
            rows.append(item)
            continue
        matched_events += 1
        best_outcome = None
        best_pick_score = 0.0
        for outcome in getattr(summary, 'outcomes', []) or []:
            score = _pick_match_score(item, outcome)
            if score > best_pick_score:
                best_pick_score = score
                best_outcome = outcome
        if best_outcome is None or best_pick_score < pick_threshold:
            rows.append(item)
            continue
        matched_picks += 1
        item['closing_decimal_price'] = round(float(best_outcome.average_price), 6)
        item['closing_collected_at_utc'] = collected_at
        item['closing_source'] = 'the_odds_api_current_odds'
        item['closing_match_confidence'] = round(event_score * 0.65 + best_pick_score * 0.35, 4)
        item['closing_market_type'] = safe_text(getattr(best_outcome, 'market', ''))
        item['closing_line_point'] = '' if getattr(best_outcome, 'point', None) is None else getattr(best_outcome, 'point')
        item['closing_bookmaker_count'] = int(getattr(best_outcome, 'source_count', 0) or 0)
        updated += 1
        rows.append(item)

    out = pd.DataFrame(rows)
    return out, {
        'updated_rows': updated,
        'checked_rows': int(len(locked)),
        'matched_events': matched_events,
        'matched_picks': matched_picks,
        'sport_key': sport_key,
        'collected_at_utc': collected_at,
        'note': 'Current odds were saved as closing_decimal_price. For best CLV, run this close to event start before the market disappears.',
    }
