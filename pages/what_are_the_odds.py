from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.sidebar_nav import render_app_sidebar

st.set_page_config(page_title='What Are the Odds', layout='wide')
LANG = render_app_sidebar('what_are_the_odds', language_key='what_are_the_odds_pro_language', selector='radio')

TEXT = {
    'en': {
        'title': 'What Are the Odds',
        'caption': 'Manual review board. Enter one row, upload CSV, paste CSV text, or use latest Pro Predictor rows. The page saves rows automatically for the next tools.',
        'info': 'Fill the single-game fields, upload a CSV, or paste CSV text. No Analyze button is required; rows save automatically when valid data is present.',
        'workflow': 'Clean path: Pro Predictor → What Are the Odds → Odds Lock → Public Proof Dashboard → Learning Memory.',
        'single_game': 'Single Game Manual Check',
        'event': 'Game / event name',
        'sport': 'Sport / league',
        'market': 'Market type',
        'pick': 'Pick / prediction',
        'start': 'Event start UTC',
        'start_help': 'Use ISO format, for example 2026-06-17T23:10:00Z.',
        'decimal': 'Decimal price',
        'american': 'American price',
        'prob': 'Model probability %',
        'source': 'Source',
        'books': 'Source count',
        'notes': 'Notes',
        'session': 'Use latest Pro Predictor session rows',
        'csv_title': 'CSV input',
        'upload': 'Upload CSV file(s)',
        'paste': 'Or paste CSV text here',
        'paste_help': 'Paste the whole CSV including the header row. This is a fallback if mobile upload fails.',
        'waiting': 'Fill event, pick, probability, and decimal or American price. Or upload/paste CSV text / use latest session rows.',
        'saved': 'Rows are saved automatically for Odds Lock Pro and the public dashboard.',
        'deduped': 'Merged rows deduplicated before handoff.',
    },
    'es': {
        'title': 'What Are the Odds',
        'caption': 'Tablero de revisión manual. Ingresa una fila, sube CSV, pega CSV o usa filas recientes de Predictor Pro. La página guarda automáticamente para las siguientes herramientas.',
        'info': 'Llena los campos, sube un CSV o pega texto CSV. No se necesita botón de análisis; las filas se guardan automáticamente cuando hay datos válidos.',
        'workflow': 'Ruta limpia: Predictor Pro → What Are the Odds → Odds Lock → Dashboard Público → Memoria.',
        'single_game': 'Revisión Manual de Un Solo Juego',
        'event': 'Juego / evento',
        'sport': 'Deporte / liga',
        'market': 'Tipo de mercado',
        'pick': 'Pick / pronóstico',
        'start': 'Inicio del evento UTC',
        'start_help': 'Usa formato ISO, por ejemplo 2026-06-17T23:10:00Z.',
        'decimal': 'Precio decimal',
        'american': 'Precio americano',
        'prob': 'Probabilidad del modelo %',
        'source': 'Fuente',
        'books': 'Número de fuentes',
        'notes': 'Notas',
        'session': 'Usar filas recientes de Predictor Pro',
        'csv_title': 'Entrada CSV',
        'upload': 'Subir archivo(s) CSV',
        'paste': 'O pega texto CSV aquí',
        'paste_help': 'Pega todo el CSV incluyendo encabezados. Esto queda como respaldo si falla la subida móvil.',
        'waiting': 'Llena evento, pick, probabilidad y precio decimal o americano. O sube/pega CSV / usa filas recientes.',
        'saved': 'Las filas se guardan automáticamente para Odds Lock Pro y el dashboard público.',
        'deduped': 'Filas combinadas deduplicadas antes de enviarlas.',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        parsed = float(str(value).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return default
    if pd.isna(parsed):
        return default
    return parsed


def decimal_from_american(value: Any) -> float | None:
    raw = safe_float(value)
    if raw is None or raw == 0:
        return None
    if raw > 0:
        return round(1.0 + raw / 100.0, 6)
    return round(1.0 + 100.0 / abs(raw), 6)


def probability_clean(value: Any) -> float | None:
    raw = safe_float(value)
    if raw is None or raw <= 0:
        return None
    if raw > 1:
        raw = raw / 100.0
    return round(max(0.0, min(1.0, raw)), 6)


def implied_probability(decimal_price: float | None) -> float | None:
    if decimal_price is None or decimal_price <= 1.0:
        return None
    return round(1.0 / decimal_price, 6)


def _clean_text(value: Any) -> str:
    if pd.isna(value):
        return ''
    return ' '.join(str(value).strip().lower().split())


def _has_rich_odds(row: pd.Series) -> bool:
    rich_cols = [
        'model_probability_clean',
        'model_probability',
        'market_implied_probability',
        'model_market_edge',
        'decimal_price',
        'odds_at_pick',
        'best_price',
        'agent_score',
    ]
    return any(col in row.index and pd.notna(row.get(col)) and str(row.get(col)).strip() not in ('', 'nan', 'None') for col in rich_cols)


def _dedupe_sort_value(row: pd.Series) -> tuple[int, int, float, str]:
    rich = 1 if _has_rich_odds(row) else 0
    lock_ready = 1 if str(row.get('lock_ready', '')).strip().lower() in ('true', '1', 'yes') else 0
    score = safe_float(row.get('agent_score'), 0.0) or 0.0
    source = _clean_text(row.get('source_file'))
    return (rich, lock_ready, score, source)


def dedupe_merged_rows(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Remove accidental duplicate imports while keeping distinct markets.

    Priority order:
    1. Exact full-row duplicates.
    2. Exact prediction-market duplicates by event_id/event, market, line and prediction.
    3. Fallback result-only rows when a richer odds row for the same event+prediction exists.

    This intentionally keeps different markets for the same game, e.g. h2h and totals.
    """
    if frame.empty:
        return frame, 0

    work = frame.copy()
    before = len(work)
    work = work.drop_duplicates().copy()

    event_key = work['event_id'].map(_clean_text) if 'event_id' in work.columns else pd.Series('', index=work.index)
    event_fallback = work['event'].map(_clean_text) if 'event' in work.columns else pd.Series('', index=work.index)
    event_key = event_key.mask(event_key.eq('') | event_key.eq('nan'), event_fallback)

    market_key = work['market_type'].map(_clean_text) if 'market_type' in work.columns else pd.Series('', index=work.index)
    line_key = work['line_point'].map(_clean_text) if 'line_point' in work.columns else pd.Series('', index=work.index)
    prediction_key = work['prediction'].map(_clean_text) if 'prediction' in work.columns else pd.Series('', index=work.index)
    sport_key = work['sport'].map(_clean_text) if 'sport' in work.columns else pd.Series('', index=work.index)

    work['_aba_event_key'] = event_key
    work['_aba_market_key'] = market_key
    work['_aba_line_key'] = line_key
    work['_aba_prediction_key'] = prediction_key
    work['_aba_sport_key'] = sport_key
    work['_aba_rich'] = work.apply(lambda row: 1 if _has_rich_odds(row) else 0, axis=1)
    work['_aba_lock'] = work.get('lock_ready', pd.Series('', index=work.index)).map(lambda value: 1 if str(value).strip().lower() in ('true', '1', 'yes') else 0)
    work['_aba_agent_score_sort'] = work.get('agent_score', pd.Series(0, index=work.index)).map(lambda value: safe_float(value, 0.0) or 0.0)

    # Drop duplicate rows for the same exact market/pick; richer rows win.
    sort_cols = ['_aba_rich', '_aba_lock', '_aba_agent_score_sort']
    work = work.sort_values(sort_cols, ascending=[False, False, False], kind='mergesort')
    exact_key_cols = ['_aba_event_key', '_aba_market_key', '_aba_line_key', '_aba_prediction_key']
    exact_mask = work[exact_key_cols].astype(str).agg('|'.join, axis=1).ne('|||')
    keyed = work[exact_mask].drop_duplicates(subset=exact_key_cols, keep='first')
    unkeyed = work[~exact_mask]
    work = pd.concat([keyed, unkeyed], ignore_index=True, sort=False)

    # If the same event+prediction exists in both rich and fallback result-only rows, keep rich.
    rich_pairs = set(
        work.loc[work['_aba_rich'].eq(1), ['_aba_event_key', '_aba_prediction_key']]
        .astype(str)
        .agg('|'.join, axis=1)
        .tolist()
    )
    pair_key = work[['_aba_event_key', '_aba_prediction_key']].astype(str).agg('|'.join, axis=1)
    keep_mask = work['_aba_rich'].eq(1) | ~pair_key.isin(rich_pairs)
    work = work[keep_mask].copy()

    helper_cols = [col for col in work.columns if col.startswith('_aba_')]
    work = work.drop(columns=helper_cols, errors='ignore').reset_index(drop=True)
    removed = before - len(work)
    return work, max(0, int(removed))


def build_manual_row() -> dict[str, Any] | None:
    event = str(st.session_state.get('wato_event') or '').strip()
    pick = str(st.session_state.get('wato_pick') or '').strip()
    if not event or not pick:
        return None
    decimal_price = safe_float(st.session_state.get('wato_decimal'))
    american_price = safe_float(st.session_state.get('wato_american'))
    price = decimal_price if decimal_price and decimal_price > 1.0 else decimal_from_american(american_price)
    prob = probability_clean(st.session_state.get('wato_probability'))
    if prob is None or price is None:
        return None
    market_prob = implied_probability(price)
    edge = round(prob - market_prob, 6) if market_prob is not None else None
    ev = round(prob * price - 1.0, 6)
    score = round(max(0.0, min(100.0, prob * 70.0 + max(-10.0, min(25.0, (edge or 0) * 300.0)) + 5.0)), 2)
    return {
        'event': event,
        'sport': str(st.session_state.get('wato_sport') or '').strip() or 'manual_single_game',
        'market_type': str(st.session_state.get('wato_market') or 'h2h'),
        'prediction': pick,
        'event_start_utc': str(st.session_state.get('wato_start') or '').strip(),
        'model_probability': prob,
        'model_probability_clean': prob,
        'decimal_price': round(float(price), 6),
        'american_odds': american_price if american_price not in (None, 0) else '',
        'market_implied_probability': market_prob if market_prob is not None else '',
        'model_market_edge': edge if edge is not None else '',
        'edge_percent': round(edge * 100.0, 2) if edge is not None else '',
        'expected_value_per_unit': ev,
        'expected_value_percent': round(ev * 100.0, 2),
        'bookmaker': str(st.session_state.get('wato_bookmaker') or '').strip() or 'manual_source',
        'odds_source': str(st.session_state.get('wato_bookmaker') or '').strip() or 'manual_source',
        'bookmaker_count': int(st.session_state.get('wato_books') or 1),
        'books': int(st.session_state.get('wato_books') or 1),
        'manual_context_notes': str(st.session_state.get('wato_notes') or '').strip(),
        'single_game_manual': True,
        'source_file': 'single_game_manual_check',
        'agent_decision': 'play_strong' if ev > 0 and prob >= 0.58 else 'research_watch',
        'agent_score': score,
        'scanner_strength_score': score,
        'recommended_action': 'review_and_route',
        'lock_ready': bool(str(st.session_state.get('wato_start') or '').strip()),
        'result_status': 'pending',
    }


def load_session_rows() -> pd.DataFrame:
    if not st.session_state.get('wato_use_session'):
        return pd.DataFrame()
    for key in ['pro_predictor_high_confidence_rows', 'pro_predictor_latest_rows', 'ara_latest_predictions']:
        rows = st.session_state.get(key) or []
        if rows:
            return pd.DataFrame(rows)
    return pd.DataFrame()


def load_uploaded_rows() -> pd.DataFrame:
    uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True, key='wato_csv_upload')
    frames: list[pd.DataFrame] = []
    if uploads:
        for upload in uploads:
            try:
                frame = pd.read_csv(upload)
                frame['source_file'] = upload.name
                frames.append(frame)
            except Exception as exc:
                st.warning(f'CSV could not be read: {exc}')
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def load_pasted_rows() -> pd.DataFrame:
    pasted = str(st.session_state.get('wato_pasted_csv') or '').strip()
    if not pasted:
        return pd.DataFrame()
    try:
        frame = pd.read_csv(StringIO(pasted))
        frame['source_file'] = 'pasted_csv_mobile_safe'
        return frame
    except Exception as exc:
        st.warning(f'Pasted CSV could not be read: {exc}')
        return pd.DataFrame()


def save_rows(frame: pd.DataFrame) -> None:
    rows = frame.to_dict('records')
    for key in ['what_are_the_odds_latest_rows', 'ara_latest_predictions', 'odds_lock_pro_candidate_rows', 'public_proof_dashboard_refresh_rows']:
        st.session_state[key] = rows
    try:
        from autonomous_betting_agent.pick_hold_store import save_held_rows
        workspace_id = str(st.session_state.get('aba_test_window_id') or 'test_01')
        save_held_rows('what_are_the_odds_latest_rows', rows, workspace_id)
        save_held_rows('ara_latest_predictions', rows, workspace_id)
    except Exception:
        pass


st.title(t('title'))
st.caption(t('caption'))
st.info(t('info'))
st.caption(t('workflow'))

st.subheader(t('single_game'))
st.text_input(t('event'), key='wato_event', placeholder='Los Angeles Dodgers at San Diego Padres')
st.text_input(t('pick'), key='wato_pick', placeholder='Los Angeles Dodgers')
c1, c2, c3 = st.columns(3)
c1.text_input(t('sport'), key='wato_sport', placeholder='MLB, NBA, WNBA, Soccer, Tennis')
c2.selectbox(t('market'), ['h2h', 'spreads', 'totals', 'prop', 'other'], key='wato_market')
c3.text_input(t('start'), key='wato_start', placeholder='2026-06-17T23:10:00Z', help=t('start_help'))
c4, c5, c6, c7 = st.columns(4)
c4.number_input(t('decimal'), min_value=0.0, max_value=1000.0, value=0.0, step=0.01, key='wato_decimal')
c5.number_input(t('american'), min_value=-5000.0, max_value=5000.0, value=0.0, step=5.0, key='wato_american')
c6.number_input(t('prob'), min_value=0.0, max_value=100.0, value=0.0, step=0.5, key='wato_probability')
c7.number_input(t('books'), min_value=0, max_value=100, value=1, step=1, key='wato_books')
st.text_input(t('source'), key='wato_bookmaker', placeholder='DraftKings / FanDuel / Bet365')
st.text_area(t('notes'), key='wato_notes', height=100, placeholder='Context notes')
st.checkbox(t('session'), value=False, key='wato_use_session')

st.subheader(t('csv_title'))
uploaded_frame = load_uploaded_rows()
st.text_area(t('paste'), key='wato_pasted_csv', height=160, help=t('paste_help'), placeholder='event,prediction,model_probability,decimal_price\nTeam A at Team B,Team A,0.61,1.91')

frames: list[pd.DataFrame] = []
manual = build_manual_row()
if manual is not None:
    frames.append(pd.DataFrame([manual]))
session_frame = load_session_rows()
if not session_frame.empty:
    frames.append(session_frame)
if not uploaded_frame.empty:
    frames.append(uploaded_frame)
pasted_frame = load_pasted_rows()
if not pasted_frame.empty:
    frames.append(pasted_frame)

if not frames:
    st.warning(t('waiting'))
    st.stop()

raw_output = pd.concat(frames, ignore_index=True, sort=False)
output, removed_count = dedupe_merged_rows(raw_output)
save_rows(output)
st.success(t('saved'))
if removed_count:
    st.info(f"{t('deduped')} Removed: {removed_count}. Final rows: {len(output)}.")
st.dataframe(output, use_container_width=True, hide_index=True)
