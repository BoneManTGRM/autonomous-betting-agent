from __future__ import annotations

import hashlib, json, uuid
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

from .final_enriched_report_pipeline import REQUIRED_REPORT_COLUMNS, PLACEHOLDER_PATTERNS, check_api_health, _first, _frame, _hash, _norm, _num, _teams, _txt


def _dec(row: Mapping[str, Any]) -> float | None:
    v = _num(_first(row, 'decimal_odds', 'decimal_price', 'best_price', 'odds_decimal', 'odds'))
    if v and v > 1: return v
    a = _num(_first(row, 'american_odds', 'moneyline'))
    return None if a is None or a == 0 else round(1 + a / 100, 6) if a > 0 else round(1 + 100 / abs(a), 6)


def _prob(row: Mapping[str, Any]) -> float | None:
    p = _num(_first(row, 'model_probability', 'model_probability_clean', 'learned_model_probability', 'final_probability', 'probability'))
    if p is None: return None
    p = p / 100 if p > 1 else p
    return round(p, 6) if 0 < p < 1 else None


def _placeholder(v: Any) -> bool:
    t = _txt(v).lower()
    return any(p.lower() in t for p in PLACEHOLDER_PATTERNS)


def _clean(v: Any) -> str:
    t = _txt(v)
    return '' if _placeholder(t) else t


def _live(row: Mapping[str, Any], flags: tuple[str, ...], fields: tuple[str, ...]) -> tuple[str, str]:
    flagged = any(_txt(row.get(k)).lower() in {'true','1','yes','live','active'} for k in flags)
    data = any(_txt(row.get(k)) and not _placeholder(row.get(k)) for k in fields)
    if flagged and data: return 'LIVE', ''
    if flagged: return 'FAILED', 'Live flag set but no usable response reached final_enriched_picks_df.'
    return 'FAILED', 'No successful live response reached final_enriched_picks_df.'


def build_final_enriched_picks_df(raw_picks_df: Any, force_refresh: bool = False) -> pd.DataFrame:
    raw = _frame(raw_picks_df); records = raw.to_dict('records') if not raw.empty else []
    now = datetime.now(timezone.utc).isoformat(); run_id = 'report_' + uuid.uuid4().hex[:12]; raw_hash = _hash(records); health = check_api_health(True); rows = []
    for i, src in enumerate(records):
        r = dict(src); away, home = _teams(r); date = _txt(_first(r,'event_date','event_start_utc','commence_time'))[:10]
        event_key = '|'.join([_norm(_first(r,'sport','league')), date] + sorted([_norm(home), _norm(away)])).strip('|') or f'event_{i}'
        dec = _dec(r); prob = _prob(r); implied = round(1/dec,6) if dec else None; edge = round(prob-implied,6) if prob is not None and implied is not None else None; ev = round(prob*dec-1,6) if prob is not None and dec else None
        full_sides = _txt(_first(r,'odds_market_sides_available','market_sides_available')).lower() in {'true','1','yes','full','complete'}; no_vig = _num(_first(r,'no_vig_implied_probability','novig_implied_probability')) if full_sides else None
        odds_live, odds_reason = _live(r, ('odds_api_live','the_odds_api_live'), ('odds_api_summary','live_odds_summary','odds_api_context'))
        odds_status, odds_source, odds_fail = ('LIVE','LIVE_API','') if odds_live == 'LIVE' else (('UPLOADED_ROW','UPLOADED_ROW', odds_reason or 'No live Odds API response reached this row; using uploaded odds.') if dec else ('MISSING','EMPTY_WITH_REASON', odds_reason or 'No odds available.'))
        news_status, news_fail = _live(r, ('newsapi_live','newsapi_enabled'), ('news_summary','newsapi_summary','breaking_news_summary')); pplx_status, pplx_fail = _live(r, ('perplexity_live','perplexity_enabled'), ('perplexity_context','perplexity_summary','perplexity_news_context')); weather_status, weather_fail = _live(r, ('weatherapi_live','weather_live'), ('weather_summary','venue_weather','weather_risk'))
        news = _clean(_first(r,'news_summary','newsapi_summary','breaking_news_summary')); pplx = _clean(_first(r,'perplexity_context','perplexity_summary','perplexity_news_context')); base_ctx = _clean(_first(r,'context','sports_context_summary','game_summary','preview_summary','analysis_summary'))
        if pplx: context, ctx_source, ctx_status, ctx_reason = pplx, 'Perplexity', pplx_status, '' if pplx_status == 'LIVE' else pplx_fail
        elif news: context, ctx_source, ctx_status, ctx_reason = news, 'NewsAPI', news_status, '' if news_status == 'LIVE' else news_fail
        elif base_ctx: context, ctx_source, ctx_status, ctx_reason = base_ctx, 'UPLOADED_ROW', 'FALLBACK_USED', 'Context came from uploaded/generated row.'
        else: context, ctx_source, ctx_status, ctx_reason = '', 'EMPTY_WITH_REASON', 'FAILED', 'Context unavailable because no real context source reached final_enriched_picks_df.'
        sport = _txt(_first(r,'sport','league')).lower(); soccer = any(x in sport for x in ('soccer','football','fifa','uefa','liga')); sdio = _txt(_first(r,'sportsdataio_event_id','sportsdataio_game_id','sdio_event_id')); fixture = _txt(_first(r,'api_football_fixture_id','api_football_match_id','fixture_id'))
        sdio_status = 'MATCHED' if sdio else ('SPORT_UNSUPPORTED' if soccer else ('API_KEY_MISSING' if not health['SportsDataIO']['key_loaded'] else 'NO_MATCH_TEAM_NAME')); fixture_status = 'MATCHED' if fixture else ('API_KEY_MISSING' if not health['API-Football']['key_loaded'] else 'NO_MATCH_TEAM_NAME')
        ev_status = 'LIVE_RECALCULATED' if odds_status == 'LIVE' and ev is not None else ('FALLBACK_CALCULATED' if dec and ev is not None else 'UNVERIFIED'); ev_source = 'calculated_from_live_odds_and_model_probability' if ev_status == 'LIVE_RECALCULATED' else ('fallback_calculated_from_uploaded_odds' if ev_status == 'FALLBACK_CALCULATED' else 'EMPTY_WITH_REASON')
        rec = 'UNVERIFIED' if ev is None or edge is None else 'BET CANDIDATE' if ev > 0 and edge > 0 else 'WATCHLIST' if (prob or 0) >= .60 and ev <= 0 else 'PASS'
        fallback = odds_status != 'LIVE' or ctx_source != 'Perplexity' or news_status != 'LIVE' or pplx_status != 'LIVE'; reason = '; '.join(x for x in [odds_fail if odds_status!='LIVE' else '', ctx_reason, news_fail if news_status!='LIVE' else '', pplx_fail if pplx_status!='LIVE' else ''] if x)
        out = dict(r); out.update({'event_id': _txt(_first(r,'event_id','game_id','fixture_id')) or event_key, 'event_key': event_key, 'duplicate_group_id': 'dup_'+hashlib.sha1(event_key.encode()).hexdigest()[:10], 'row_id': hashlib.sha1(json.dumps(r, sort_keys=True, default=str).encode()).hexdigest()[:12], 'raw_input_hash': raw_hash, 'enrichment_input_hash': '', 'sport': _txt(_first(r,'sport','league')), 'league': _txt(_first(r,'league','competition')), 'event_date': date, 'start_time': _txt(_first(r,'start_time','event_start_utc','commence_time')), 'home_team': home, 'away_team': away, 'normalized_home_team': _norm(home), 'normalized_away_team': _norm(away), 'selected_market': _txt(_first(r,'selected_market','market_type','market')), 'selected_pick': _txt(_first(r,'selected_pick','prediction','pick','selection')), 'bookmaker': _txt(_first(r,'bookmaker','sportsbook')), 'decimal_odds': dec, 'decimal_price': dec, 'american_odds': None if not dec else int(round((dec-1)*100)) if dec>=2 else int(round(-100/(dec-1))), 'odds_source': odds_source, 'odds_status': odds_status, 'odds_last_refresh': now if odds_status=='LIVE' else '', 'odds_failure_reason': odds_fail, 'odds_market_sides_available': 'FULL' if full_sides else 'INCOMPLETE', 'model_probability': prob, 'model_probability_source': 'model_probability' if prob is not None else 'EMPTY_WITH_REASON', 'confidence_source': 'model_probability' if prob is not None else 'EMPTY_WITH_REASON', 'confidence_status': 'AVAILABLE' if prob is not None else 'MISSING', 'raw_implied_probability': implied, 'no_vig_implied_probability': no_vig, 'no_vig_status': 'CALCULATED' if no_vig is not None else 'UNAVAILABLE_MARKET_INCOMPLETE', 'edge': edge, 'model_market_edge': edge, 'no_vig_edge': round(prob-no_vig,6) if prob is not None and no_vig is not None else None, 'EV': ev, 'expected_value_per_unit': ev, 'ev_source': ev_source, 'ev_status': ev_status, 'fair_odds': round(1/prob,6) if prob else None, 'target_odds': round((1/prob)*1.02,6) if prob else None, 'recommendation_status': rec, 'final_decision': rec, 'confidence_tier': _txt(_first(r,'confidence_tier','confidence_bucket','public_confidence')), 'units': _txt(_first(r,'units','recommended_stake_units','suggested_stake_units')) or ('0.5' if rec=='BET CANDIDATE' else '0.0'), 'risk_label': _txt(_first(r,'risk_label','risk','risk_level')) or ('FALLBACK MODE' if fallback else 'STANDARD'), 'risk_reasons': _txt(_first(r,'risk_reasons','risk_reason','risk_notes')) or ('Fallback data used; verify before betting.' if fallback else ''), 'sportsdataio_event_id': sdio, 'sportsdataio_match_status': sdio_status, 'sportsdataio_failure_reason': '' if sdio else ('SportsDataIO unsupported for this soccer/international row; use API-Football if matched.' if soccer else 'No SportsDataIO event id reached final_enriched_picks_df.'), 'api_football_fixture_id': fixture, 'api_football_match_status': fixture_status, 'api_football_failure_reason': '' if fixture else 'No API-Football fixture id reached final_enriched_picks_df.', 'weather_status': weather_status, 'weather_summary': _clean(_first(r,'weather_summary','venue_weather','weather_risk')), 'weather_failure_reason': weather_fail if weather_status!='LIVE' else '', 'news_status': news_status, 'news_summary': news, 'news_failure_reason': news_fail if news_status!='LIVE' else '', 'perplexity_status': pplx_status, 'perplexity_context': pplx, 'perplexity_failure_reason': pplx_fail if pplx_status!='LIVE' else '', 'context': context, 'sports_context_summary': context or ('Context unavailable because: '+ctx_reason), 'context_source': ctx_source, 'context_status': ctx_status, 'context_failure_reason': ctx_reason, 'fallback_used': fallback, 'fallback_reason': reason, 'cache_status': 'CACHE_CLEARED' if force_refresh else 'LIVE_REFRESH', 'enrichment_status': 'FALLBACK_USED' if fallback else 'LIVE_ENRICHED', 'data_freshness_status': 'CURRENT_RUN', 'last_api_refresh_time': now, 'report_run_id': report_run_id, 'report_source': 'final_enriched_picks_df', 'field_provenance_json': json.dumps({'decimal_odds': odds_source, 'EV': ev_source, 'context': ctx_source}, sort_keys=True), 'source_trace_json': json.dumps({'raw_row_index': i, 'event_key': event_key}, sort_keys=True), 'api_health_json': json.dumps(health, sort_keys=True)})
        out.setdefault('injury_notes',''); out.setdefault('team_snapshot_home',''); out.setdefault('team_snapshot_away',''); out.setdefault('matchup_notes',''); out.setdefault('pro_bettor_evidence',''); out.setdefault('reparodynamics_status','OBSERVATION_ONLY'); out.setdefault('reparodynamics_notes','No Reparodynamics annotation reached this row.'); out.setdefault('repair_flags','')
        out['enrichment_input_hash'] = _hash({k: out.get(k) for k in REQUIRED_REPORT_COLUMNS if k not in {'enrichment_input_hash','report_run_id','last_api_refresh_time'}}); rows.append(out)
    df = pd.DataFrame(rows)
    for c in REQUIRED_REPORT_COLUMNS:
        if c not in df.columns: df[c] = ''
    return df


def validate_report_pipeline(df: Any) -> list[str]:
    frame = _frame(df); errors = []
    if frame.empty: return ['final_enriched_picks_df is empty']
    for c in REQUIRED_REPORT_COLUMNS:
        if c not in frame.columns: errors.append('Missing required column: '+c)
    for c in ('report_run_id','last_api_refresh_time','raw_input_hash','enrichment_input_hash'):
        if c not in frame or frame[c].map(_txt).eq('').any(): errors.append(c+' missing')
    if 'report_source' in frame and not frame['report_source'].astype(str).eq('final_enriched_picks_df').all(): errors.append('report_source must be final_enriched_picks_df')
    return errors


def prepare_report_rows(rows: Any, force_refresh: bool = False) -> list[dict[str, Any]]:
    df = _frame(rows)
    if force_refresh or df.empty or 'report_source' not in df.columns or not df['report_source'].astype(str).eq('final_enriched_picks_df').all(): df = build_final_enriched_picks_df(df, force_refresh)
    errs = validate_report_pipeline(df)
    if errs: raise ValueError('Report pipeline validation failed: ' + '; '.join(errs))
    return df.to_dict('records')


def install() -> None:
    try:
        from . import magazine_book_export as m
    except Exception:
        return
    if getattr(m, '_aba_final_enriched_pipeline_guard', False): return
    original_pages = m.render_full_magazine_book_pages; original_page = m.render_full_pick_magazine_page; original_pairs = m._pairs
    def guarded_pages(picks, *args, **kwargs): return original_pages(prepare_report_rows(picks, bool(kwargs.pop('force_refresh', False))), *args, **kwargs)
    def guarded_page(pick, *args, **kwargs): return original_page(prepare_report_rows([pick], bool(kwargs.pop('force_refresh', False)))[0], *args, **kwargs)
    def guarded_odds(row):
        data = row if isinstance(row, Mapping) else getattr(row, 'to_dict', lambda: {})(); status = _txt(data.get('odds_status'))
        return 'LIVE_API Odds API' if status == 'LIVE' else 'UPLOADED_ROW odds' if status == 'UPLOADED_ROW' else (status or 'EMPTY_WITH_REASON')
    def guarded_context(row):
        data = row if isinstance(row, Mapping) else getattr(row, 'to_dict', lambda: {})(); ctx = _txt(data.get('context') or data.get('sports_context_summary')); reason = _txt(data.get('context_failure_reason'))
        return [ctx] if ctx and not _placeholder(ctx) else ['Context unavailable because: ' + (reason or 'no context reached final_enriched_picks_df')]
    def guarded_pairs(row, lang):
        data = row if isinstance(row, Mapping) else getattr(row, 'to_dict', lambda: {})()
        return (original_pairs(row, lang) + [('SOURCE', _txt(data.get('report_source')) or 'final_enriched_picks_df'), ('RUN', _txt(data.get('report_run_id'))[:18]), ('CACHE', _txt(data.get('cache_status')))])[:5]
    m.render_full_magazine_book_pages = guarded_pages; m.render_full_pick_magazine_page = guarded_page; m._odds_row_label = guarded_odds; m._headline_context_lines = guarded_context; m._pairs = guarded_pairs; m._aba_final_enriched_pipeline_guard = True
