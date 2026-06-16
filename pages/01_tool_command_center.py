from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.agent_decision_engine import build_agent_decisions
from autonomous_betting_agent.game_intelligence_tools import agent_answer, display_columns, enrich_game_intelligence, line_shop_table, operator_daily_report, shadow_proof_frame
from autonomous_betting_agent.odds_accuracy_tools import enrich_odds_accuracy, odds_accuracy_summary
from autonomous_betting_agent.odds_lock_tools import prepare_lock_candidates
from autonomous_betting_agent.row_normalizer import normalize_frame
from autonomous_betting_agent.scanner_strength import score_scanner_frame
from autonomous_betting_agent.tool_sidebar import PAGE_GUIDES, WORKFLOW, proof_sidebar_snapshot, session_state_summary, render_tool_sidebar

st.set_page_config(page_title='Command Center', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='tool_command_center_language') == 'Español' else 'en'
render_tool_sidebar('start_here', 'Español' if LANG == 'es' else 'English')

TEXT = {
    'en': {
        'title': 'Command Center',
        'caption': 'One daily operator cockpit: load a game or session rows, run odds/value review, inspect the game card, review blockers, create shadow review rows, then move official-ready rows to Odds Lock Pro.',
        'note': 'Use this page as the normal daily screen. Specialist pages remain available for deeper work.',
        'single': 'Single-game quick input',
        'event': 'Game / event name',
        'sport': 'Sport / league',
        'market': 'Market type',
        'pick': 'Pick / prediction',
        'start': 'Event start UTC',
        'bookmaker': 'Bookmaker / source',
        'decimal': 'Decimal odds',
        'american': 'American odds',
        'prob': 'Model probability %',
        'books': 'Book count',
        'notes': 'Notes',
        'line_shop': 'Optional line-shopping prices',
        'analyze': 'Analyze single game',
        'loaded': 'Single game loaded.',
        'missing': 'Enter event, pick, probability, and decimal or American odds.',
        'use_session': 'Use latest session rows',
        'bulk': 'Advanced CSV / bulk input',
        'upload': 'Upload CSV file(s)',
        'paste': 'Paste CSV text',
        'waiting': 'Load a single game, session rows, uploaded CSV, or pasted CSV to run the command board.',
        'route': 'Recommended route',
        'board': 'Operator board',
        'card': 'Game card',
        'line': 'Line shopping',
        'ask': 'Ask the agent',
        'review': 'Review / do-not-promote rows',
        'shadow': 'Shadow review',
        'official': 'Official-ready preview',
        'client': 'Client-safe view',
        'report': 'Daily report',
        'tools': 'Advanced tool map',
    },
    'es': {
        'title': 'Centro de Comando',
        'caption': 'Cockpit diario: carga un juego o filas, revisa cuotas/valor, tarjeta, bloqueos, shadow review y luego pasa filas oficiales a Odds Lock Pro.',
        'note': 'Usa esta página como pantalla diaria. Las páginas avanzadas siguen disponibles.',
        'single': 'Entrada rápida de un juego',
        'event': 'Juego / evento',
        'sport': 'Deporte / liga',
        'market': 'Tipo de mercado',
        'pick': 'Pick / pronóstico',
        'start': 'Inicio UTC',
        'bookmaker': 'Casa / fuente',
        'decimal': 'Cuota decimal',
        'american': 'Cuota americana',
        'prob': 'Probabilidad modelo %',
        'books': 'Número de casas',
        'notes': 'Notas',
        'line_shop': 'Precios opcionales',
        'analyze': 'Analizar juego',
        'loaded': 'Juego cargado.',
        'missing': 'Ingresa evento, pick, probabilidad y cuota.',
        'use_session': 'Usar filas recientes',
        'bulk': 'CSV / entrada masiva avanzada',
        'upload': 'Subir CSV(s)',
        'paste': 'Pegar CSV',
        'waiting': 'Carga un juego, sesión, CSV o texto CSV.',
        'route': 'Ruta recomendada',
        'board': 'Tablero operador',
        'card': 'Tarjeta',
        'line': 'Line shopping',
        'ask': 'Preguntar al agente',
        'review': 'Revisión / no promover',
        'shadow': 'Shadow review',
        'official': 'Vista previa oficial',
        'client': 'Vista cliente',
        'report': 'Reporte diario',
        'tools': 'Mapa avanzado',
    },
}

CLIENT_COLUMNS = ['event_start_utc', 'event', 'sport', 'market_type', 'prediction', 'decimal_price', 'best_available_price', 'best_available_book', 'model_probability', 'edge_percent', 'expected_value_percent', 'robust_expected_value_percent', 'odds_trust_grade', 'game_intelligence_grade', 'operator_next_step', 'game_intelligence_card']
REVIEW_COLUMNS = ['event', 'prediction', 'operator_next_step', 'data_quality_blockers', 'data_quality_warnings', 'odds_quality_flags', 'needed_info', 'minimum_line_value_status', 'market_disagreement_flag', 'robust_value_rating', 'recommended_action']


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def num(value: Any) -> float | None:
    try:
        parsed = float(str(value).replace('%', '').replace(',', '').strip())
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return parsed


def decimal_from_american(value: Any) -> float | None:
    odds = num(value)
    if odds is None:
        return None
    if odds >= 100:
        return round(1.0 + odds / 100.0, 6)
    if odds <= -100:
        return round(1.0 + 100.0 / abs(odds), 6)
    return None


def session_frame() -> pd.DataFrame:
    frames = []
    sources = [
        ('game_intelligence_latest_rows', 'Game Intelligence'),
        ('what_are_the_odds_latest_rows', 'What Are the Odds'),
        ('pro_predictor_latest_rows', 'Pro Predictor'),
        ('pro_predictor_high_confidence_rows', 'High Confidence'),
        ('scanner_pro_latest_rows', 'Scanner Pro'),
    ]
    for key, label in sources:
        rows = st.session_state.get(key) or []
        if rows:
            frame = pd.DataFrame(rows)
            frame['command_center_source'] = label
            frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def single_game_form() -> pd.DataFrame:
    st.subheader(t('single'))
    with st.form('command_center_single_form', clear_on_submit=False):
        top = st.columns(2)
        event = top[0].text_input(t('event'), placeholder='Los Angeles Dodgers at San Diego Padres')
        sport = top[1].text_input(t('sport'), placeholder='MLB')
        mid = st.columns(4)
        market = mid[0].selectbox(t('market'), ['h2h', 'spreads', 'totals', 'prop', 'other'])
        pick = mid[1].text_input(t('pick'), placeholder='Los Angeles Dodgers')
        start = mid[2].text_input(t('start'), placeholder='2026-06-17T23:10:00Z')
        bookmaker = mid[3].text_input(t('bookmaker'), placeholder='DraftKings')
        odds = st.columns(5)
        decimal = odds[0].number_input(t('decimal'), min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        american = odds[1].number_input(t('american'), min_value=-5000.0, max_value=5000.0, value=0.0, step=5.0)
        probability = odds[2].number_input(t('prob'), min_value=0.0, max_value=100.0, value=0.0, step=0.5)
        books = odds[3].number_input(t('books'), min_value=0, max_value=100, value=1, step=1)
        closing = odds[4].number_input('Closing decimal price', min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        st.caption(t('line_shop'))
        line_cols = st.columns(6)
        dk = line_cols[0].number_input('DraftKings', min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        fd = line_cols[1].number_input('FanDuel', min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        bet365 = line_cols[2].number_input('Bet365', min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        pinnacle = line_cols[3].number_input('Pinnacle', min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        caesars = line_cols[4].number_input('Caesars', min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        mgm = line_cols[5].number_input('MGM', min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
        notes = st.text_area(t('notes'), placeholder='Starter confirmed; no major injuries; weather normal; price still playable')
        submitted = st.form_submit_button(t('analyze'), use_container_width=True)
    if not submitted:
        return pd.DataFrame()
    price = float(decimal) if float(decimal) > 1.0 else decimal_from_american(american)
    prob = float(probability) / 100.0 if float(probability) > 1.0 else float(probability)
    if not event.strip() or not pick.strip() or price is None or not (0.0 < prob < 1.0):
        st.warning(t('missing'))
        return pd.DataFrame()
    row = {
        'event': event.strip(), 'sport': sport.strip() or 'manual_single_game', 'market_type': market,
        'prediction': pick.strip(), 'event_start_utc': start.strip(), 'bookmaker': bookmaker.strip() or 'manual_source',
        'odds_source': bookmaker.strip() or 'manual_source', 'decimal_price': price, 'model_probability': round(prob, 6),
        'model_probability_clean': round(prob, 6), 'bookmaker_count': int(books), 'books': int(books),
        'closing_decimal_price': round(float(closing), 6) if float(closing) > 1.0 else '',
        'draftkings_decimal_price': dk if dk > 1 else '', 'fanduel_decimal_price': fd if fd > 1 else '',
        'bet365_decimal_price': bet365 if bet365 > 1 else '', 'pinnacle_decimal_price': pinnacle if pinnacle > 1 else '',
        'caesars_decimal_price': caesars if caesars > 1 else '', 'mgm_decimal_price': mgm if mgm > 1 else '',
        'manual_context_notes': notes.strip(), 'single_game_manual': True, 'source_file': 'command_center', 'result_status': 'pending',
    }
    st.success(t('loaded'))
    return pd.DataFrame([row])


def read_inputs() -> pd.DataFrame:
    frames = []
    single = single_game_form()
    if not single.empty:
        frames.append(single)
    if st.checkbox(t('use_session'), value=bool(st.session_state.get('what_are_the_odds_latest_rows') or st.session_state.get('pro_predictor_latest_rows'))):
        session = session_frame()
        if not session.empty:
            frames.append(session)
    with st.expander(t('bulk'), expanded=False):
        uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
        if uploads:
            for upload in uploads:
                frame = pd.read_csv(upload)
                frame['source_file'] = upload.name
                frames.append(frame)
        pasted = st.text_area(t('paste'), height=120)
        if pasted.strip():
            frame = pd.read_csv(StringIO(pasted.strip()))
            frame['source_file'] = 'pasted_csv'
            frames.append(frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def prepare_board(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = normalize_frame(frame)
    odds = enrich_odds_accuracy(normalized)
    scored = score_scanner_frame(odds)
    decisions = build_agent_decisions(scored)
    decisions = score_scanner_frame(decisions)
    return enrich_game_intelligence(decisions)


def review_rows(board: pd.DataFrame) -> pd.DataFrame:
    mask = pd.Series(False, index=board.index)
    for column in ['data_quality_blockers', 'data_quality_warnings', 'odds_quality_flags', 'needed_info']:
        if column in board.columns:
            mask = mask | board[column].fillna('').astype(str).str.len().gt(0)
    for column in ['operator_next_step', 'minimum_line_value_status', 'robust_value_rating', 'recommended_action']:
        if column in board.columns:
            mask = mask | board[column].fillna('').astype(str).str.contains('skip|review|rescan|missing|below_fair|negative|uncertain', case=False, regex=True)
    out = board[mask].copy()
    cols = [col for col in REVIEW_COLUMNS if col in out.columns]
    return out[cols] if cols else out


def client_view(board: pd.DataFrame) -> pd.DataFrame:
    out = board.copy()
    for column in CLIENT_COLUMNS:
        if column not in out.columns:
            out[column] = ''
    return out[CLIENT_COLUMNS]


def recommended_route(board: pd.DataFrame, official: pd.DataFrame, review: pd.DataFrame) -> list[str]:
    if board.empty:
        return ['Load a game or session rows.', 'Run analysis.', 'Review blockers before official proof.']
    if not official.empty:
        return ['Official-ready rows exist.', 'Open Odds Lock Pro.', 'Create future-only proof rows before event start.']
    shadow = int(board.get('shadow_proof_ready', pd.Series(dtype=bool)).fillna(False).astype(bool).sum())
    if shadow:
        return ['Shadow candidates exist.', 'Fix blockers preventing official readiness.', 'Then move clean rows to Odds Lock Pro.']
    if not review.empty:
        return ['Rows need review.', 'Fix missing fields, compare more books, or wait for better price.', 'Do not promote weak rows.']
    return ['Continue monitoring.', 'Use Public Proof Dashboard after official rows are saved.', 'Grade finished rows after final scores.']


def page_rows() -> list[dict[str, str]]:
    rows = []
    for key, values in PAGE_GUIDES.items():
        guide = values.get(LANG, values['en'])
        rows.append({'Tool': guide['name'], 'Purpose': guide['purpose'], 'Next': guide['next'], 'Avoid': guide['avoid']})
    return rows


st.title(t('title'))
st.caption(t('caption'))
st.info(t('note'))
raw = read_inputs()
if raw.empty:
    snapshot = proof_sidebar_snapshot()
    st.warning(t('waiting'))
    st.json(snapshot)
    st.stop()

board = prepare_board(raw)
st.session_state['command_center_latest_rows'] = board.to_dict('records')
st.session_state['game_intelligence_latest_rows'] = board.to_dict('records')
st.session_state['what_are_the_odds_latest_rows'] = board.to_dict('records')
st.session_state['ara_latest_predictions'] = board.to_dict('records')

shadow = shadow_proof_frame(board)
official_preview = prepare_lock_candidates(board, include_watch=True, strict=False, require_future=True)
official_ready = official_preview[official_preview['official_lock_ready'].astype(bool)].copy() if not official_preview.empty and 'official_lock_ready' in official_preview.columns else pd.DataFrame()
review = review_rows(board)
accuracy = odds_accuracy_summary(board)

cols = st.columns(8)
cols[0].metric('Rows', len(board))
cols[1].metric('Official-ready', len(official_ready))
cols[2].metric('Shadow', len(shadow))
cols[3].metric('Review', len(review))
cols[4].metric('Positive robust EV', accuracy.get('robust_positive_ev_rows', 0))
cols[5].metric('Lock candidates', accuracy.get('lock_candidate_rows', 0))
cols[6].metric('Avg odds score', accuracy.get('avg_odds_accuracy_score'))
cols[7].metric('Future rows', accuracy.get('future_rows', 0))

st.subheader(t('route'))
for item in recommended_route(board, official_ready, review):
    st.write(f'- {item}')

options = [f"{row.get('prediction', 'Pick')} — {row.get('event', 'Event')}" for row in board.to_dict(orient='records')]
selected_label = st.selectbox('Selected game', options)
selected = board.iloc[options.index(selected_label)].to_dict()

tabs = st.tabs([t('card'), t('board'), t('line'), t('ask'), t('review'), t('shadow'), t('official'), t('client'), t('report'), t('tools')])
with tabs[0]:
    st.markdown(selected.get('game_intelligence_card', 'No card available.'))
with tabs[1]:
    columns = display_columns(board)
    st.dataframe(board[columns] if columns else board, use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(line_shop_table(selected), use_container_width=True, hide_index=True)
with tabs[3]:
    question = st.text_input('Question', placeholder='What odds do I need? Why is this not ready? What is the next step?')
    st.write(agent_answer(selected, question))
with tabs[4]:
    st.dataframe(review, use_container_width=True, hide_index=True)
with tabs[5]:
    st.dataframe(shadow, use_container_width=True, hide_index=True)
    st.download_button('Download shadow review CSV', shadow.to_csv(index=False), file_name='command_center_shadow_review.csv', mime='text/csv')
with tabs[6]:
    st.dataframe(official_preview, use_container_width=True, hide_index=True)
    st.caption('Create official proof rows in Odds Lock Pro after reviewing this preview.')
with tabs[7]:
    client = client_view(board)
    st.dataframe(client, use_container_width=True, hide_index=True)
    st.download_button('Download client-safe CSV', client.to_csv(index=False), file_name='command_center_client_view.csv', mime='text/csv')
with tabs[8]:
    report = operator_daily_report(board)
    st.text_area(t('report'), value=report, height=420)
    st.download_button('Download daily report', report, file_name='command_center_daily_report.md', mime='text/markdown')
with tabs[9]:
    st.dataframe(pd.DataFrame(page_rows()), use_container_width=True, hide_index=True)
    st.subheader('Session handoff')
    st.dataframe(session_state_summary(), use_container_width=True, hide_index=True)
    st.subheader('Workflow')
    st.dataframe(pd.DataFrame({'step': range(1, len(WORKFLOW) + 1), 'tool': WORKFLOW}), use_container_width=True, hide_index=True)

st.download_button('Download full command board CSV', board.to_csv(index=False), file_name='command_center_board.csv', mime='text/csv')
