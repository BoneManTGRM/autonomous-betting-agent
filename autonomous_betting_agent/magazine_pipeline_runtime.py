from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

from .final_enriched_report_pipeline import (
    PLACEHOLDER_PATTERNS,
    REQUIRED_REPORT_COLUMNS,
    _first,
    _frame,
    _hash,
    _norm,
    _num,
    _teams,
    _txt,
    check_api_health,
)


def _decimal_odds(row: Mapping[str, Any]) -> float | None:
    value = _num(_first(row, 'decimal_odds', 'decimal_price', 'best_price', 'odds_decimal', 'odds'))
    if value and value > 1:
        return value
    american = _num(_first(row, 'american_odds', 'moneyline'))
    if american is None or american == 0:
        return None
    return round(1 + american / 100, 6) if american > 0 else round(1 + 100 / abs(american), 6)


def _american_from_decimal(decimal_odds: float | None) -> int | None:
    if decimal_odds is None or decimal_odds <= 1:
        return None
    return int(round((decimal_odds - 1) * 100)) if decimal_odds >= 2 else int(round(-100 / (decimal_odds - 1)))


def _model_probability(row: Mapping[str, Any]) -> float | None:
    value = _num(_first(row, 'model_probability', 'model_probability_clean', 'learned_model_probability', 'final_probability', 'probability'))
    if value is None:
        return None
    value = value / 100 if value > 1 else value
    return round(value, 6) if 0 < value < 1 else None


def _is_placeholder(value: Any) -> bool:
    text = _txt(value).lower()
    return any(pattern.lower() in text for pattern in PLACEHOLDER_PATTERNS)


def _clean(value: Any) -> str:
    text = _txt(value)
    return '' if _is_placeholder(text) else text


def _live_status(row: Mapping[str, Any], flags: tuple[str, ...], fields: tuple[str, ...]) -> tuple[str, str]:
    flagged = any(_txt(row.get(key)).lower() in {'true', '1', 'yes', 'live', 'active'} for key in flags)
    has_payload = any(_txt(row.get(key)) and not _is_placeholder(row.get(key)) for key in fields)
    if flagged and has_payload:
        return 'LIVE', ''
    if flagged:
        return 'FAILED', 'Live flag was set but no usable provider payload reached final_enriched_picks_df.'
    return 'FAILED', 'No successful provider response reached final_enriched_picks_df.'


def _event_key(row: Mapping[str, Any], home: str, away: str, index: int) -> str:
    date = _txt(_first(row, 'event_date', 'event_start_utc', 'commence_time', 'start_time'))[:10]
    key = '|'.join([_norm(_first(row, 'sport', 'league')), date] + sorted([_norm(home), _norm(away)])).strip('|')
    return key or f'event_{index}'


def _recommendation(probability: float | None, ev: float | None, edge: float | None) -> str:
    if probability is None or ev is None or edge is None:
        return 'UNVERIFIED'
    if ev > 0 and edge > 0:
        return 'BET CANDIDATE'
    if probability >= 0.60 and ev <= 0:
        return 'WATCHLIST'
    return 'PASS' if ev <= 0 else 'NO PLAY'


def build_final_enriched_picks_df(raw_picks_df: Any, force_refresh: bool = False) -> pd.DataFrame:
    raw = _frame(raw_picks_df)
    records = raw.to_dict('records') if not raw.empty else []
    now = datetime.now(timezone.utc).isoformat()
    report_run_id = 'report_' + uuid.uuid4().hex[:12]
    raw_hash = _hash(records)
    api_health = check_api_health(mask_secrets=True)
    rows: list[dict[str, Any]] = []

    for index, source_row in enumerate(records):
        row = dict(source_row)
        away_team, home_team = _teams(row)
        event_key = _event_key(row, home_team, away_team, index)
        decimal_odds = _decimal_odds(row)
        model_probability = _model_probability(row)
        raw_implied = round(1 / decimal_odds, 6) if decimal_odds else None
        edge = round(model_probability - raw_implied, 6) if model_probability is not None and raw_implied is not None else None
        ev = round(model_probability * decimal_odds - 1, 6) if model_probability is not None and decimal_odds else None
        full_sides = _txt(_first(row, 'odds_market_sides_available', 'market_sides_available')).lower() in {'true', '1', 'yes', 'full', 'complete'}
        no_vig = _num(_first(row, 'no_vig_implied_probability', 'novig_implied_probability')) if full_sides else None

        odds_live, odds_reason = _live_status(row, ('odds_api_live', 'the_odds_api_live'), ('odds_api_summary', 'live_odds_summary', 'odds_api_context'))
        if odds_live == 'LIVE':
            odds_status, odds_source, odds_failure = 'LIVE', 'LIVE_API', ''
        elif decimal_odds:
            odds_status, odds_source, odds_failure = 'UPLOADED_ROW', 'UPLOADED_ROW', odds_reason
        else:
            odds_status, odds_source, odds_failure = 'MISSING', 'EMPTY_WITH_REASON', odds_reason

        news_status, news_failure = _live_status(row, ('newsapi_live', 'newsapi_enabled'), ('news_summary', 'newsapi_summary', 'breaking_news_summary'))
        perplexity_status, perplexity_failure = _live_status(row, ('perplexity_live', 'perplexity_enabled'), ('perplexity_context', 'perplexity_summary', 'perplexity_news_context'))
        weather_status, weather_failure = _live_status(row, ('weatherapi_live', 'weather_live'), ('weather_summary', 'venue_weather', 'weather_risk'))
        news_summary = _clean(_first(row, 'news_summary', 'newsapi_summary', 'breaking_news_summary'))
        perplexity_context = _clean(_first(row, 'perplexity_context', 'perplexity_summary', 'perplexity_news_context'))
        uploaded_context = _clean(_first(row, 'context', 'sports_context_summary', 'game_summary', 'preview_summary', 'analysis_summary'))

        if perplexity_context:
            context, context_source, context_status, context_reason = perplexity_context, 'Perplexity', perplexity_status, '' if perplexity_status == 'LIVE' else perplexity_failure
        elif news_summary:
            context, context_source, context_status, context_reason = news_summary, 'NewsAPI', news_status, '' if news_status == 'LIVE' else news_failure
        elif uploaded_context:
            context, context_source, context_status, context_reason = uploaded_context, 'UPLOADED_ROW', 'FALLBACK_USED', 'Context came from the uploaded/generated row.'
        else:
            context, context_source, context_status, context_reason = '', 'EMPTY_WITH_REASON', 'FAILED', 'No real context source reached final_enriched_picks_df.'

        sport_text = _txt(_first(row, 'sport', 'league')).lower()
        soccer = any(token in sport_text for token in ('soccer', 'football', 'fifa', 'uefa', 'liga'))
        sportsdataio_id = _txt(_first(row, 'sportsdataio_event_id', 'sportsdataio_game_id', 'sdio_event_id'))
        api_football_id = _txt(_first(row, 'api_football_fixture_id', 'api_football_match_id', 'fixture_id'))
        sportsdataio_status = 'MATCHED' if sportsdataio_id else ('SPORT_UNSUPPORTED' if soccer else ('API_KEY_MISSING' if not api_health['SportsDataIO']['key_loaded'] else 'NO_MATCH_TEAM_NAME'))
        api_football_status = 'MATCHED' if api_football_id else ('API_KEY_MISSING' if not api_health['API-Football']['key_loaded'] else 'NO_MATCH_TEAM_NAME')

        ev_status = 'LIVE_RECALCULATED' if odds_status == 'LIVE' and ev is not None else ('FALLBACK_CALCULATED' if decimal_odds and ev is not None else 'UNVERIFIED')
        ev_source = 'calculated_from_live_odds_and_model_probability' if ev_status == 'LIVE_RECALCULATED' else ('fallback_calculated_from_uploaded_odds' if ev_status == 'FALLBACK_CALCULATED' else 'EMPTY_WITH_REASON')
        fallback_used = odds_status != 'LIVE' or context_source != 'Perplexity' or news_status != 'LIVE' or perplexity_status != 'LIVE'
        fallback_reason = '; '.join(part for part in [odds_failure if odds_status != 'LIVE' else '', context_reason, news_failure if news_status != 'LIVE' else '', perplexity_failure if perplexity_status != 'LIVE' else ''] if part)
        recommendation = _recommendation(model_probability, ev, edge)
        provenance = {'decimal_odds': odds_source, 'EV': ev_source, 'context': context_source, 'news_summary': 'NewsAPI' if news_status == 'LIVE' and news_summary else 'EMPTY_WITH_REASON', 'perplexity_context': 'Perplexity' if perplexity_status == 'LIVE' and perplexity_context else 'EMPTY_WITH_REASON'}

        output = dict(row)
        output.update({
            'event_id': _txt(_first(row, 'event_id', 'game_id', 'fixture_id')) or event_key,
            'event_key': event_key,
            'duplicate_group_id': 'dup_' + hashlib.sha1(event_key.encode()).hexdigest()[:10],
            'row_id': hashlib.sha1(json.dumps(row, sort_keys=True, default=str).encode()).hexdigest()[:12],
            'raw_input_hash': raw_hash,
            'enrichment_input_hash': '',
            'sport': _txt(_first(row, 'sport', 'league')),
            'league': _txt(_first(row, 'league', 'competition')),
            'event_date': _txt(_first(row, 'event_date', 'event_start_utc', 'commence_time'))[:10],
            'start_time': _txt(_first(row, 'start_time', 'event_start_utc', 'commence_time')),
            'home_team': home_team,
            'away_team': away_team,
            'normalized_home_team': _norm(home_team),
            'normalized_away_team': _norm(away_team),
            'selected_market': _txt(_first(row, 'selected_market', 'market_type', 'market')),
            'selected_pick': _txt(_first(row, 'selected_pick', 'prediction', 'pick', 'selection')),
            'bookmaker': _txt(_first(row, 'bookmaker', 'sportsbook')),
            'decimal_odds': decimal_odds,
            'decimal_price': decimal_odds,
            'american_odds': _num(_first(row, 'american_odds', 'moneyline')) or _american_from_decimal(decimal_odds),
            'odds_source': odds_source,
            'odds_status': odds_status,
            'odds_last_refresh': now if odds_status == 'LIVE' else '',
            'odds_failure_reason': odds_failure,
            'odds_market_sides_available': 'FULL' if full_sides else 'INCOMPLETE',
            'model_probability': model_probability,
            'model_probability_source': 'model_probability' if model_probability is not None else 'EMPTY_WITH_REASON',
            'confidence_source': 'model_probability' if model_probability is not None else 'EMPTY_WITH_REASON',
            'confidence_status': 'AVAILABLE' if model_probability is not None else 'MISSING',
            'raw_implied_probability': raw_implied,
            'no_vig_implied_probability': no_vig,
            'no_vig_status': 'CALCULATED' if no_vig is not None else 'UNAVAILABLE_MARKET_INCOMPLETE',
            'edge': edge,
            'model_market_edge': edge,
            'no_vig_edge': round(model_probability - no_vig, 6) if model_probability is not None and no_vig is not None else None,
            'EV': ev,
            'expected_value_per_unit': ev,
            'ev_source': ev_source,
            'ev_status': ev_status,
            'fair_odds': round(1 / model_probability, 6) if model_probability else None,
            'target_odds': round((1 / model_probability) * 1.02, 6) if model_probability else None,
            'confidence_tier': _txt(_first(row, 'confidence_tier', 'confidence_bucket', 'public_confidence')),
            'recommendation_status': recommendation,
            'final_decision': recommendation,
            'units': _txt(_first(row, 'units', 'recommended_stake_units', 'suggested_stake_units')) or ('0.5' if recommendation == 'BET CANDIDATE' else '0.0'),
            'risk_label': _txt(_first(row, 'risk_label', 'risk', 'risk_level')) or ('FALLBACK MODE' if fallback_used else 'STANDARD'),
            'risk_reasons': _txt(_first(row, 'risk_reasons', 'risk_reason', 'risk_notes')) or ('Fallback data used; verify before betting.' if fallback_used else ''),
            'sportsdataio_event_id': sportsdataio_id,
            'sportsdataio_match_status': sportsdataio_status,
            'sportsdataio_failure_reason': '' if sportsdataio_id else ('SportsDataIO unsupported for this soccer/international row; use API-Football if matched.' if soccer else 'No SportsDataIO event id reached final_enriched_picks_df.'),
            'api_football_fixture_id': api_football_id,
            'api_football_match_status': api_football_status,
            'api_football_failure_reason': '' if api_football_id else 'No API-Football fixture id reached final_enriched_picks_df.',
            'weather_status': weather_status,
            'weather_summary': _clean(_first(row, 'weather_summary', 'venue_weather', 'weather_risk')),
            'weather_failure_reason': weather_failure if weather_status != 'LIVE' else '',
            'news_status': news_status,
            'news_summary': news_summary,
            'news_failure_reason': news_failure if news_status != 'LIVE' else '',
            'perplexity_status': perplexity_status,
            'perplexity_context': perplexity_context,
            'perplexity_failure_reason': perplexity_failure if perplexity_status != 'LIVE' else '',
            'context': context,
            'sports_context_summary': context or ('Context unavailable because: ' + context_reason),
            'context_source': context_source,
            'context_status': context_status,
            'context_failure_reason': context_reason,
            'fallback_used': bool(fallback_used),
            'fallback_reason': fallback_reason,
            'cache_status': 'CACHE_CLEARED' if force_refresh else 'LIVE_REFRESH',
            'enrichment_status': 'FALLBACK_USED' if fallback_used else 'LIVE_ENRICHED',
            'data_freshness_status': 'CURRENT_RUN',
            'last_api_refresh_time': now,
            'report_run_id': report_run_id,
            'report_source': 'final_enriched_picks_df',
            'field_provenance_json': json.dumps(provenance, sort_keys=True),
            'source_trace_json': json.dumps({'raw_row_index': index, 'event_key': event_key}, sort_keys=True),
            'api_health_json': json.dumps(api_health, sort_keys=True),
        })
        for key, value in {
            'injury_notes': '', 'team_snapshot_home': '', 'team_snapshot_away': '', 'matchup_notes': '',
            'pro_bettor_evidence': '', 'reparodynamics_status': 'OBSERVATION_ONLY',
            'reparodynamics_notes': 'No Reparodynamics annotation reached this row.', 'repair_flags': '',
        }.items():
            output.setdefault(key, value)
        output['enrichment_input_hash'] = _hash({key: output.get(key) for key in REQUIRED_REPORT_COLUMNS if key not in {'enrichment_input_hash', 'report_run_id', 'last_api_refresh_time'}})
        rows.append(output)

    final_enriched_picks_df = pd.DataFrame(rows)
    for column in REQUIRED_REPORT_COLUMNS:
        if column not in final_enriched_picks_df.columns:
            final_enriched_picks_df[column] = ''
    return final_enriched_picks_df


def validate_report_pipeline(df: Any) -> list[str]:
    frame = _frame(df)
    if frame.empty:
        return ['final_enriched_picks_df is empty']
    errors: list[str] = []
    for column in REQUIRED_REPORT_COLUMNS:
        if column not in frame.columns:
            errors.append('Missing required column: ' + column)
    for column in ('report_run_id', 'last_api_refresh_time', 'raw_input_hash', 'enrichment_input_hash'):
        if column not in frame or frame[column].map(_txt).eq('').any():
            errors.append(column + ' missing')
    if 'report_source' in frame and not frame['report_source'].astype(str).eq('final_enriched_picks_df').all():
        errors.append('report_source must be final_enriched_picks_df')
    if 'no_vig_status' in frame and 'odds_market_sides_available' in frame:
        bad = frame['no_vig_status'].astype(str).eq('CALCULATED') & ~frame['odds_market_sides_available'].astype(str).eq('FULL')
        if bool(bad.any()):
            errors.append('no-vig calculated with incomplete market sides')
    return errors


def prepare_report_rows(rows: Any, force_refresh: bool = False) -> list[dict[str, Any]]:
    frame = _frame(rows)
    if force_refresh or frame.empty or 'report_source' not in frame.columns or not frame['report_source'].astype(str).eq('final_enriched_picks_df').all():
        frame = build_final_enriched_picks_df(frame, force_refresh=force_refresh)
    errors = validate_report_pipeline(frame)
    if errors:
        raise ValueError('Report pipeline validation failed: ' + '; '.join(errors))
    return frame.to_dict('records')


def install() -> None:
    try:
        from . import magazine_book_export as module
    except Exception:
        return
    if getattr(module, '_aba_final_enriched_pipeline_guard', False):
        return
    original_pages = module.render_full_magazine_book_pages
    original_page = module.render_full_pick_magazine_page
    original_pairs = module._pairs

    def guarded_pages(picks, *args, **kwargs):
        force_refresh = bool(kwargs.pop('force_refresh', False))
        return original_pages(prepare_report_rows(picks, force_refresh=force_refresh), *args, **kwargs)

    def guarded_page(pick, *args, **kwargs):
        force_refresh = bool(kwargs.pop('force_refresh', False))
        row = prepare_report_rows([pick], force_refresh=force_refresh)[0]
        return original_page(row, *args, **kwargs)

    def guarded_odds(row):
        data = row if isinstance(row, Mapping) else getattr(row, 'to_dict', lambda: {})()
        status = _txt(data.get('odds_status'))
        if status == 'LIVE':
            return 'LIVE_API Odds API'
        if status == 'UPLOADED_ROW':
            return 'UPLOADED_ROW odds'
        return status or 'EMPTY_WITH_REASON'

    def guarded_context(row):
        data = row if isinstance(row, Mapping) else getattr(row, 'to_dict', lambda: {})()
        context = _txt(data.get('context') or data.get('sports_context_summary'))
        reason = _txt(data.get('context_failure_reason'))
        return [context] if context and not _is_placeholder(context) else ['Context unavailable because: ' + (reason or 'no context reached final_enriched_picks_df')]

    def guarded_pairs(row, lang):
        data = row if isinstance(row, Mapping) else getattr(row, 'to_dict', lambda: {})()
        diagnostics = [
            ('SOURCE', _txt(data.get('report_source')) or 'final_enriched_picks_df'),
            ('RUN', _txt(data.get('report_run_id'))[:18]),
            ('CACHE', _txt(data.get('cache_status'))),
        ]
        return (diagnostics + original_pairs(row, lang))[:5]

    module.render_full_magazine_book_pages = guarded_pages
    module.render_full_pick_magazine_page = guarded_page
    module._odds_row_label = guarded_odds
    module._headline_context_lines = guarded_context
    module._pairs = guarded_pairs
    module._aba_final_enriched_pipeline_guard = True
