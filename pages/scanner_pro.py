from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.live_odds import list_sports, scan_market

st.set_page_config(page_title='Scanner Pro', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='scanner_pro_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Scanner Pro',
        'caption': 'One consolidated scanner for all supported sports, leagues, markets, books, and live odds feeds.',
        'info': 'Use Scanner Pro for live market discovery. Use Pro Predictor for final prediction scoring and Learning Memory for durable training.',
        'api_key': 'Odds API key',
        'missing_key': 'Missing Odds API key. Add THE_ODDS_API_KEY or ODDS_API_KEY in Streamlit secrets.',
        'scan_scope': 'Scan scope',
        'all_sports': 'All active sports',
        'one_sport': 'One sport/league',
        'sport_search': 'Sport search',
        'max_sports': 'Max sports to scan',
        'max_events': 'Max events per sport',
        'regions': 'Bookmaker regions',
        'markets': 'Markets',
        'min_books': 'Minimum books',
        'run': 'Run Scanner Pro',
        'rows': 'Rows',
        'sports': 'Sports',
        'events': 'Events',
        'books': 'Avg books',
        'best_price_rows': 'Rows with best price',
        'moneyline': 'Moneyline outcomes',
        'spreads': 'Spreads',
        'totals': 'Totals',
        'download': 'Download Scanner Pro CSV',
        'no_rows': 'No rows returned. Try fewer filters or another sport/region.',
        'stored': 'Scanner rows saved in session for Market Finder Pro and Learning Memory review.',
    },
    'es': {
        'title': 'Scanner Pro',
        'caption': 'Escáner único para todos los deportes, ligas, mercados, casas de apuestas y cuotas en vivo compatibles.',
        'info': 'Usa Scanner Pro para descubrir mercados en vivo. Usa Pro Predictor para la calificación final de predicciones y Memoria de Aprendizaje para entrenamiento duradero.',
        'api_key': 'Clave de Odds API',
        'missing_key': 'Falta la clave de Odds API. Agrega THE_ODDS_API_KEY u ODDS_API_KEY en los secretos de Streamlit.',
        'scan_scope': 'Alcance del escaneo',
        'all_sports': 'Todos los deportes activos',
        'one_sport': 'Un deporte/liga',
        'sport_search': 'Buscar deporte',
        'max_sports': 'Máximo de deportes a escanear',
        'max_events': 'Máximo de eventos por deporte',
        'regions': 'Regiones de casas de apuestas',
        'markets': 'Mercados',
        'min_books': 'Mínimo de casas de apuestas',
        'run': 'Ejecutar Scanner Pro',
        'rows': 'Filas',
        'sports': 'Deportes',
        'events': 'Eventos',
        'books': 'Promedio de casas',
        'best_price_rows': 'Filas con mejor cuota',
        'moneyline': 'Resultados moneyline',
        'spreads': 'Spreads',
        'totals': 'Totales',
        'download': 'Descargar CSV de Scanner Pro',
        'no_rows': 'No se encontraron filas. Prueba con menos filtros u otro deporte/región.',
        'stored': 'Las filas del escáner se guardaron en la sesión para Market Finder Pro y revisión en Memoria de Aprendizaje.',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def get_secret(*names: str) -> str:
    for name in names:
        try:
            value = str(st.secrets.get(name, '')).strip()
            if value:
                return value
        except Exception:
            pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


def h2h_rows(summary: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    event = f'{summary.away_team} at {summary.home_team}' if summary.away_team and summary.home_team else summary.event_id
    for outcome in summary.outcomes:
        rows.append({
            'scanner_source': 'scanner_pro_live_odds',
            'event_id': summary.event_id,
            'event': event,
            'sport': summary.sport_title,
            'sport_key': summary.sport_key,
            'event_start_utc': summary.commence_time,
            'home_team': summary.home_team,
            'away_team': summary.away_team,
            'market_type': 'h2h',
            'prediction': outcome.name,
            'model_probability': round(float(outcome.normalized_probability), 6),
            'market_probability': round(float(outcome.normalized_probability), 6),
            'decimal_price': outcome.best_price or outcome.average_price,
            'average_price': outcome.average_price,
            'best_price': outcome.best_price,
            'worst_price': outcome.worst_price,
            'price_range': outcome.price_range,
            'bookmaker': outcome.best_bookmaker,
            'bookmaker_count': outcome.source_count,
            'books': outcome.source_count,
            'market_overround': summary.market_overround,
            'odds_source': 'The Odds API',
            'decision': 'scanner_only',
        })
    return rows


def line_rows(summary: Any, attr: str, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    event = f'{summary.away_team} at {summary.home_team}' if summary.away_team and summary.home_team else summary.event_id
    for line in getattr(summary, attr) or []:
        rows.append({
            'scanner_source': 'scanner_pro_live_odds',
            'event_id': summary.event_id,
            'event': event,
            'sport': summary.sport_title,
            'sport_key': summary.sport_key,
            'event_start_utc': summary.commence_time,
            'home_team': summary.home_team,
            'away_team': summary.away_team,
            'market_type': label,
            'prediction': line.name,
            'point': line.point,
            'decimal_price': line.best_price or line.average_price,
            'average_price': line.average_price,
            'best_price': line.best_price,
            'worst_price': line.worst_price,
            'price_range': line.price_range,
            'bookmaker': line.best_bookmaker,
            'bookmaker_count': line.source_count,
            'books': line.source_count,
            'odds_source': 'The Odds API',
            'decision': 'scanner_only',
        })
    return rows


def scan_to_frame(api_key: str, sports_to_scan: list[str], regions: str, markets: str, max_events: int, min_books: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for sport_key in sports_to_scan:
        try:
            summaries = scan_market(api_key, sport_key=sport_key, regions=regions, markets=markets, max_events=max_events)
            for summary in summaries:
                rows.extend(h2h_rows(summary))
                rows.extend(line_rows(summary, 'spreads', 'spreads'))
                rows.extend(line_rows(summary, 'totals', 'totals'))
        except Exception as exc:
            skipped.append({'sport_key': sport_key, 'error': str(exc)[:300]})
    frame = pd.DataFrame(rows)
    if not frame.empty and min_books > 1 and 'bookmaker_count' in frame.columns:
        frame = frame[pd.to_numeric(frame['bookmaker_count'], errors='coerce').fillna(0) >= min_books]
    st.session_state['scanner_pro_skipped'] = skipped
    return frame


st.title(t('title'))
st.caption(t('caption'))
st.info(t('info'))
api_key = get_secret('THE_ODDS_API_KEY', 'ODDS_API_KEY')
st.caption(f"{t('api_key')}: {'Configured' if api_key else 'Missing'}")
if not api_key:
    st.error(t('missing_key'))
    st.stop()

scope = st.radio(t('scan_scope'), [t('all_sports'), t('one_sport')], horizontal=True)
regions = st.multiselect(t('regions'), ['us', 'eu', 'uk', 'au'], default=['us'])
markets = st.multiselect(t('markets'), ['h2h', 'spreads', 'totals'], default=['h2h'])
max_events = st.number_input(t('max_events'), min_value=1, max_value=100, value=20, step=5)
min_books = st.number_input(t('min_books'), min_value=1, max_value=20, value=1, step=1)

sports = list_sports(api_key, include_all=False)
sports_df = pd.DataFrame([asdict(item) for item in sports])
search = st.text_input(t('sport_search'), value='')
if search.strip():
    mask = sports_df.astype(str).agg(' '.join, axis=1).str.lower().str.contains(search.strip().lower(), regex=False, na=False)
    sports_df = sports_df[mask]

if scope == t('all_sports'):
    max_sports = st.number_input(t('max_sports'), min_value=1, max_value=100, value=min(20, max(1, len(sports_df))), step=1)
    sports_to_scan = sports_df['key'].head(int(max_sports)).tolist() if 'key' in sports_df else []
else:
    options = sports_df['key'].tolist() if 'key' in sports_df else []
    selected = st.multiselect(t('one_sport'), options, default=options[:1])
    sports_to_scan = selected

with st.expander(t('sports'), expanded=False):
    st.dataframe(sports_df, use_container_width=True, hide_index=True)

if st.button(t('run'), type='primary', use_container_width=True):
    result = scan_to_frame(api_key, sports_to_scan, ','.join(regions), ','.join(markets), int(max_events), int(min_books))
    st.session_state['scanner_pro_latest_rows'] = result.to_dict('records')
    st.session_state['ara_latest_predictions'] = result.to_dict('records')
    st.session_state['ara_latest_predictions_source'] = 'Scanner Pro'
    st.session_state['ara_latest_predictions_saved_at'] = pd.Timestamp.utcnow().isoformat()
else:
    result = pd.DataFrame(st.session_state.get('scanner_pro_latest_rows', []))

if result.empty:
    st.warning(t('no_rows'))
    skipped = pd.DataFrame(st.session_state.get('scanner_pro_skipped', []))
    if not skipped.empty:
        st.dataframe(skipped, use_container_width=True, hide_index=True)
    st.stop()

st.success(t('stored'))
cols = st.columns(5)
cols[0].metric(t('rows'), len(result))
cols[1].metric(t('sports'), result['sport_key'].nunique() if 'sport_key' in result else 0)
cols[2].metric(t('events'), result['event_id'].nunique() if 'event_id' in result else 0)
cols[3].metric(t('books'), round(float(pd.to_numeric(result.get('bookmaker_count', pd.Series(dtype=float)), errors='coerce').fillna(0).mean()), 2))
cols[4].metric(t('best_price_rows'), int(result.get('best_price', pd.Series(dtype=str)).fillna('').astype(str).str.strip().ne('').sum()) if 'best_price' in result else 0)

tabs = st.tabs([t('moneyline'), t('spreads'), t('totals'), 'All'])
with tabs[0]:
    st.dataframe(result[result['market_type'].eq('h2h')] if 'market_type' in result else result, use_container_width=True, hide_index=True)
with tabs[1]:
    st.dataframe(result[result['market_type'].eq('spreads')] if 'market_type' in result else pd.DataFrame(), use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(result[result['market_type'].eq('totals')] if 'market_type' in result else pd.DataFrame(), use_container_width=True, hide_index=True)
with tabs[3]:
    st.dataframe(result, use_container_width=True, hide_index=True)

st.download_button(t('download'), result.to_csv(index=False), file_name='scanner_pro_live_markets.csv', mime='text/csv')
