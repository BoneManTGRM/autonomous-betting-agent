from __future__ import annotations

from io import StringIO
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.agent_decision_engine import build_agent_decisions
from autonomous_betting_agent.commercial_platform_tools import load_persistent_ledger
from autonomous_betting_agent.game_intelligence_tools import agent_answer, display_columns, enrich_game_intelligence, line_shop_table, operator_daily_report, shadow_proof_frame
from autonomous_betting_agent.odds_accuracy_tools import enrich_odds_accuracy, odds_accuracy_summary
from autonomous_betting_agent.odds_lock_tools import prepare_lock_candidates
from autonomous_betting_agent.row_normalizer import normalize_frame, safe_text
from autonomous_betting_agent.scanner_strength import score_scanner_frame
from autonomous_betting_agent.tool_sidebar import PAGE_GUIDES, WORKFLOW, proof_sidebar_snapshot, session_state_summary, render_tool_sidebar
from autonomous_betting_agent.ui_language import render_language_selector

st.set_page_config(page_title='Command Center', layout='wide')
LANG = render_language_selector(key='tool_command_center_language')
render_tool_sidebar('start_here', 'Español' if LANG == 'es' else 'English')

TEXT = {
    'en': {
        'title': 'Command Center',
        'caption': 'One daily operator cockpit: load a game or session rows, run odds/value review, inspect the game card, review blockers, create shadow review rows, then move official-ready rows to Odds Lock Pro.',
        'note': 'Use this page as the normal daily screen. Specialist pages remain available for deeper work.',
        'single': 'Single-game quick input', 'event': 'Game / event name', 'sport': 'Sport / league', 'market': 'Market type', 'pick': 'Pick / prediction', 'start': 'Event start UTC', 'bookmaker': 'Bookmaker / source', 'decimal': 'Decimal odds', 'american': 'American odds', 'prob': 'Model probability %', 'books': 'Book count', 'notes': 'Notes', 'line_shop': 'Optional line-shopping prices', 'analyze': 'Analyze single game', 'loaded': 'Single game loaded.', 'missing': 'Enter event, pick, probability, and decimal or American odds.',
        'use_session': 'Use latest session rows', 'bulk': 'Advanced CSV / bulk input', 'upload': 'Upload CSV file(s)', 'paste': 'Paste CSV text', 'waiting': 'Load a single game, session rows, uploaded CSV, or pasted CSV to run the command board.', 'route': 'Recommended route',
        'board': 'Operator board', 'card': 'Game card', 'explain': 'Why / why not', 'line': 'Line shopping', 'ask': 'Ask the agent', 'review': 'Review rows', 'shadow': 'Shadow review', 'official': 'Official-ready preview', 'client': 'Client-safe view', 'calibration': 'Calibration', 'clv': 'CLV tracker', 'confidence': 'Confidence', 'memory': 'Memory influence', 'report': 'Daily report', 'tools': 'Advanced tool map',
        'question': 'Question', 'official_caption': 'Create official proof rows in Odds Lock Pro after reviewing this preview.', 'session_handoff': 'Session handoff', 'workflow': 'Workflow', 'download_shadow': 'Download shadow review CSV', 'download_client': 'Download client-safe CSV', 'download_report': 'Download daily report', 'download_full': 'Download full command board CSV',
    },
    'es': {
        'title': 'Centro de Comando',
        'caption': 'Cockpit diario: carga un juego o filas, revisa cuotas/valor, tarjeta, bloqueos, shadow review y luego pasa filas oficiales a Odds Lock Pro.',
        'note': 'Usa esta página como pantalla diaria. Las páginas avanzadas siguen disponibles.',
        'single': 'Entrada rápida de un juego', 'event': 'Juego / evento', 'sport': 'Deporte / liga', 'market': 'Tipo de mercado', 'pick': 'Pick / pronóstico', 'start': 'Inicio UTC', 'bookmaker': 'Casa / fuente', 'decimal': 'Cuota decimal', 'american': 'Cuota americana', 'prob': 'Probabilidad modelo %', 'books': 'Número de casas', 'notes': 'Notas', 'line_shop': 'Precios opcionales', 'analyze': 'Analizar juego', 'loaded': 'Juego cargado.', 'missing': 'Ingresa evento, pick, probabilidad y cuota.',
        'use_session': 'Usar filas recientes', 'bulk': 'CSV / entrada masiva avanzada', 'upload': 'Subir CSV(s)', 'paste': 'Pegar CSV', 'waiting': 'Carga un juego, sesión, CSV o texto CSV.', 'route': 'Ruta recomendada',
        'board': 'Tablero operador', 'card': 'Tarjeta', 'explain': 'Por qué / por qué no', 'line': 'Line shopping', 'ask': 'Preguntar al agente', 'review': 'Filas de revisión', 'shadow': 'Shadow review', 'official': 'Vista previa oficial', 'client': 'Vista cliente', 'calibration': 'Calibración', 'clv': 'Tracker CLV', 'confidence': 'Confianza', 'memory': 'Influencia de memoria', 'report': 'Reporte diario', 'tools': 'Mapa avanzado',
        'question': 'Pregunta', 'official_caption': 'Crea filas de prueba oficial en Odds Lock Pro después de revisar esta vista.', 'session_handoff': 'Handoff de sesión', 'workflow': 'Flujo', 'download_shadow': 'Descargar CSV shadow', 'download_client': 'Descargar CSV cliente', 'download_report': 'Descargar reporte diario', 'download_full': 'Descargar tablero completo CSV',
    },
}

CLIENT_COLUMNS = ['event_start_utc', 'event', 'sport', 'market_type', 'prediction', 'decimal_price', 'best_available_price', 'best_available_book', 'model_probability', 'edge_percent', 'expected_value_percent', 'robust_expected_value_percent', 'odds_trust_grade', 'game_intelligence_grade', 'operator_next_step', 'game_intelligence_card']
REVIEW_COLUMNS = ['event', 'prediction', 'operator_next_step', 'data_quality_blockers', 'data_quality_warnings', 'odds_quality_flags', 'needed_info', 'minimum_line_value_status', 'market_disagreement_flag', 'robust_value_rating', 'recommended_action']
BUCKETS = [0.0, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 1.01]
BUCKET_LABELS = ['<50%', '50-55%', '55-60%', '60-65%', '65-70%', '70-75%', '75-80%', '80%+']


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


def prob(value: Any) -> float | None:
    parsed = num(value)
    if parsed is None:
        return None
    if 1.0 < parsed <= 100.0:
        parsed /= 100.0
    return parsed if 0.0 < parsed < 1.0 else None


def decimal_from_american(value: Any) -> float | None:
    odds = num(value)
    if odds is None:
        return None
    if odds >= 100:
        return round(1.0 + odds / 100.0, 6)
    if odds <= -100:
        return round(1.0 + 100.0 / abs(odds), 6)
    return None


def result_status(value: Any) -> str:
    text = safe_text(value).lower()
    if text in {'win', 'won', 'w', '1', '1.0', 'true', 'correct', 'hit'}:
        return 'win'
    if text in {'loss', 'lost', 'l', '0', '0.0', 'false', 'incorrect', 'miss'}:
        return 'loss'
    return ''


def session_frame() -> pd.DataFrame:
    frames = []
    sources = [('game_intelligence_latest_rows', 'Game Intelligence'), ('what_are_the_odds_latest_rows', 'What Are the Odds'), ('pro_predictor_latest_rows', 'Pro Predictor'), ('pro_predictor_high_confidence_rows', 'High Confidence'), ('scanner_pro_latest_rows', 'Scanner Pro')]
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
        closing = odds[4].number_input('Closing decimal price' if LANG == 'en' else 'Cuota decimal de cierre', min_value=0.0, max_value=1000.0, value=0.0, step=0.01)
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
    probability_value = float(probability) / 100.0 if float(probability) > 1.0 else float(probability)
    if not event.strip() or not pick.strip() or price is None or not (0.0 < probability_value < 1.0):
        st.warning(t('missing'))
        return pd.DataFrame()
    row = {'event': event.strip(), 'sport': sport.strip() or 'manual_single_game', 'market_type': market, 'prediction': pick.strip(), 'event_start_utc': start.strip(), 'bookmaker': bookmaker.strip() or 'manual_source', 'odds_source': bookmaker.strip() or 'manual_source', 'decimal_price': price, 'model_probability': round(probability_value, 6), 'model_probability_clean': round(probability_value, 6), 'bookmaker_count': int(books), 'books': int(books), 'closing_decimal_price': round(float(closing), 6) if float(closing) > 1.0 else '', 'draftkings_decimal_price': dk if dk > 1 else '', 'fanduel_decimal_price': fd if fd > 1 else '', 'bet365_decimal_price': bet365 if bet365 > 1 else '', 'pinnacle_decimal_price': pinnacle if pinnacle > 1 else '', 'caesars_decimal_price': caesars if caesars > 1 else '', 'mgm_decimal_price': mgm if mgm > 1 else '', 'manual_context_notes': notes.strip(), 'single_game_manual': True, 'source_file': 'command_center', 'result_status': 'pending'}
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
        return ['Load a game or session rows.', 'Run analysis.', 'Review blockers before official proof.'] if LANG == 'en' else ['Carga un juego o filas de sesión.', 'Corre el análisis.', 'Revisa bloqueos antes de prueba oficial.']
    if not official.empty:
        return ['Official-ready rows exist.', 'Open Odds Lock Pro.', 'Create future-only proof rows before event start.'] if LANG == 'en' else ['Hay filas listas para oficial.', 'Abre Odds Lock Pro.', 'Crea prueba futura antes del inicio.']
    shadow = int(board.get('shadow_proof_ready', pd.Series(dtype=bool)).fillna(False).astype(bool).sum())
    if shadow:
        return ['Shadow candidates exist.', 'Fix blockers preventing official readiness.', 'Then move clean rows to Odds Lock Pro.'] if LANG == 'en' else ['Hay candidatos shadow.', 'Corrige bloqueos antes de oficial.', 'Luego mueve filas limpias a Odds Lock Pro.']
    if not review.empty:
        return ['Rows need review.', 'Fix missing fields, compare more books, or wait for better price.', 'Do not promote weak rows.'] if LANG == 'en' else ['Filas necesitan revisión.', 'Corrige campos, compara más casas o espera mejor precio.', 'No promociones filas débiles.']
    return ['Continue monitoring.', 'Use Public Proof Dashboard after official rows are saved.', 'Grade finished rows after final scores.'] if LANG == 'en' else ['Sigue monitoreando.', 'Usa Dashboard Público después de guardar prueba oficial.', 'Califica filas terminadas con scores finales.']


def page_rows() -> list[dict[str, str]]:
    rows = []
    for key, values in PAGE_GUIDES.items():
        guide = values.get(LANG, values['en'])
        rows.append({'Tool' if LANG == 'en' else 'Herramienta': guide['name'], 'Purpose' if LANG == 'en' else 'Propósito': guide['purpose'], 'Next' if LANG == 'en' else 'Siguiente': guide['next'], 'Avoid' if LANG == 'en' else 'Evitar': guide['avoid']})
    return rows


def resolved_rows(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    data = normalize_frame(frame) if frame is not None and not frame.empty else load_persistent_ledger()
    if data is None or data.empty:
        return pd.DataFrame()
    rows = []
    for row in data.to_dict(orient='records'):
        status = result_status(row.get('result_status') or row.get('result') or row.get('outcome'))
        p = prob(row.get('model_probability') or row.get('model_probability_clean') or row.get('probability'))
        if status not in {'win', 'loss'} or p is None:
            continue
        item = dict(row)
        item['_won'] = 1 if status == 'win' else 0
        item['_prob'] = p
        rows.append(item)
    return pd.DataFrame(rows)


def calibration_table(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    data = resolved_rows(frame)
    if data.empty:
        return pd.DataFrame(columns=['bucket', 'rows', 'wins', 'losses', 'avg_predicted', 'actual_win_rate', 'gap', 'brier'])
    data['_bucket'] = pd.cut(data['_prob'], bins=BUCKETS, labels=BUCKET_LABELS, include_lowest=True, right=False)
    rows = []
    for label in BUCKET_LABELS:
        group = data[data['_bucket'].astype(str).eq(label)]
        if group.empty:
            rows.append({'bucket': label, 'rows': 0, 'wins': 0, 'losses': 0, 'avg_predicted': None, 'actual_win_rate': None, 'gap': None, 'brier': None})
        else:
            p = pd.to_numeric(group['_prob'], errors='coerce')
            w = pd.to_numeric(group['_won'], errors='coerce')
            rows.append({'bucket': label, 'rows': len(group), 'wins': int(w.sum()), 'losses': int(len(group) - int(w.sum())), 'avg_predicted': round(float(p.mean()), 4), 'actual_win_rate': round(float(w.mean()), 4), 'gap': round(float(w.mean() - p.mean()), 4), 'brier': round(float(((p - w) ** 2).mean()), 5)})
    return pd.DataFrame(rows)


def calibration_summary_local(frame: pd.DataFrame | None = None) -> dict[str, Any]:
    data = resolved_rows(frame)
    if data.empty:
        return {'resolved': 0, 'status': 'not_enough_data', 'hit_rate': None, 'avg_predicted': None, 'brier': None}
    w = pd.to_numeric(data['_won'], errors='coerce')
    p = pd.to_numeric(data['_prob'], errors='coerce')
    hit = float(w.mean())
    avg = float(p.mean())
    if len(data) < 25:
        status = 'tiny_sample_directional_only'
    elif abs(hit - avg) <= 0.035:
        status = 'well_calibrated_so_far'
    elif hit < avg:
        status = 'overconfident_so_far'
    else:
        status = 'underconfident_so_far'
    return {'resolved': int(len(data)), 'status': status, 'hit_rate': round(hit, 4), 'avg_predicted': round(avg, 4), 'brier': round(float(((p - w) ** 2).mean()), 5)}


def clv_table(frame: pd.DataFrame | None = None) -> pd.DataFrame:
    data = normalize_frame(frame) if frame is not None and not frame.empty else load_persistent_ledger()
    rows = []
    for row in data.to_dict(orient='records') if data is not None and not data.empty else []:
        locked = num(row.get('locked_decimal_price') or row.get('decimal_price') or row.get('best_available_price'))
        closing = num(row.get('closing_decimal_price'))
        if locked is None or closing is None or locked <= 1.0 or closing <= 1.0:
            continue
        value = locked / closing - 1.0
        rows.append({'event': safe_text(row.get('event')), 'prediction': safe_text(row.get('prediction')), 'locked_decimal_price': round(locked, 4), 'closing_decimal_price': round(closing, 4), 'closing_value_percent': round(value * 100.0, 3), 'beat_closing_price': bool(value > 0), 'result_status': safe_text(row.get('result_status'))})
    return pd.DataFrame(rows)


def pick_explanation(row: dict[str, Any]) -> str:
    reasons = []
    risks = []
    p = prob(row.get('model_probability') or row.get('model_probability_clean'))
    implied = prob(row.get('market_implied_probability'))
    edge = num(row.get('edge_percent'))
    ev = num(row.get('robust_expected_value_percent') or row.get('expected_value_percent'))
    if p is not None:
        reasons.append(('model probability' if LANG == 'en' else 'probabilidad modelo') + f' {p * 100:.1f}%')
    if implied is not None:
        reasons.append(('market implied' if LANG == 'en' else 'mercado implícito') + f' {implied * 100:.1f}%')
    if edge is not None and edge > 0:
        reasons.append(('positive edge' if LANG == 'en' else 'edge positivo') + f' +{edge:.1f} pts')
    if ev is not None and ev > 0:
        reasons.append(('positive value' if LANG == 'en' else 'valor positivo') + f' +{ev:.1f}%')
    best = num(row.get('best_available_price'))
    if best is not None:
        reasons.append(('best price' if LANG == 'en' else 'mejor cuota') + f' {best:.2f}')
    for key in ['data_quality_blockers', 'data_quality_warnings', 'odds_quality_flags', 'needed_info']:
        value = safe_text(row.get(key))
        if value:
            risks.append(value)
    lines = [f"### {('Why this pick' if LANG == 'en' else 'Por qué este pick')}: {safe_text(row.get('prediction'))}", f"**{('Game' if LANG == 'en' else 'Juego')}:** {safe_text(row.get('event'))}", f"**{('Reasons' if LANG == 'en' else 'Razones')}:**"]
    lines.extend([f'- {item}' for item in (reasons or [('Not enough value data yet' if LANG == 'en' else 'Aún faltan datos de valor')])])
    lines.append(f"**{('Risks/checks' if LANG == 'en' else 'Riesgos/revisiones')}:**")
    lines.extend([f'- {item}' for item in (risks or [('No major blocker shown, verify source before lock' if LANG == 'en' else 'No aparece bloqueo mayor, verifica la fuente antes de bloquear')])])
    return '\n'.join(lines)


def review_explanation(row: dict[str, Any]) -> str:
    blockers = []
    for key in ['data_quality_blockers', 'data_quality_warnings', 'odds_quality_flags', 'needed_info']:
        text = safe_text(row.get(key))
        if text:
            blockers.extend([x.strip() for x in text.replace('|', ';').split(';') if x.strip()])
    action = safe_text(row.get('operator_next_step') or row.get('recommended_action'))
    if action and any(term in action for term in ['skip', 'review', 'rescan', 'missing']):
        blockers.append(action)
    header = 'Do not promote yet because:' if LANG == 'en' else 'No promover todavía porque:'
    if not blockers:
        return 'No clear blocker detected. Still verify odds, source, start time, injuries, and market movement.' if LANG == 'en' else 'No se detectó bloqueo claro. Aun así verifica cuotas, fuente, inicio, lesiones y movimiento de mercado.'
    return header + '\n' + '\n'.join(f'- {item}' for item in list(dict.fromkeys(blockers))[:10])


def confidence_explanation(row: dict[str, Any]) -> str:
    grade = safe_text(row.get('game_intelligence_grade') or row.get('odds_trust_grade') or row.get('confidence_tier')) or 'Unrated'
    supports = []
    limits = []
    if (num(row.get('robust_expected_value_per_unit')) or 0) > 0:
        supports.append('positive robust EV' if LANG == 'en' else 'EV robusto positivo')
    if (num(row.get('line_shop_count')) or 0) >= 3:
        supports.append('multiple books checked' if LANG == 'en' else 'varias casas revisadas')
    if row.get('data_quality_wall_pass') is True or safe_text(row.get('data_quality_wall_pass')).lower() in {'true', '1', 'yes'}:
        supports.append('data quality wall passed' if LANG == 'en' else 'pasó pared de calidad')
    if safe_text(row.get('data_quality_blockers')):
        limits.append('required data blockers exist' if LANG == 'en' else 'hay bloqueos de datos')
    if safe_text(row.get('data_quality_warnings')):
        limits.append('warnings need review' if LANG == 'en' else 'advertencias requieren revisión')
    if safe_text(row.get('market_disagreement_flag')) == 'extreme_review_required':
        limits.append('extreme model-vs-market disagreement' if LANG == 'en' else 'desacuerdo extremo modelo vs mercado')
    return '\n'.join([f"**{('Confidence grade' if LANG == 'en' else 'Grado de confianza')}:** {grade}", f"**{('Supports confidence' if LANG == 'en' else 'Apoya confianza')}:**", *[f'- {x}' for x in (supports or [('not enough positive confidence evidence yet' if LANG == 'en' else 'aún falta evidencia positiva')])], f"**{('Limits confidence' if LANG == 'en' else 'Limita confianza')}:**", *[f'- {x}' for x in (limits or [('no major limiter shown' if LANG == 'en' else 'no aparece limitador mayor')])]])


def memory_influence(row: dict[str, Any]) -> dict[str, Any]:
    data = resolved_rows(load_persistent_ledger())
    p = prob(row.get('model_probability') or row.get('model_probability_clean'))
    if data.empty or p is None:
        return {'message': 'No usable memory influence yet.' if LANG == 'en' else 'Aún no hay influencia de memoria útil.', 'similar_rows': 0}
    subset = data[(data['_prob'] >= p - 0.075) & (data['_prob'] <= p + 0.075)]
    if subset.empty:
        return {'message': 'No similar finished pattern found yet.' if LANG == 'en' else 'Aún no hay patrón finalizado similar.', 'similar_rows': 0}
    actual = float(pd.to_numeric(subset['_won'], errors='coerce').mean())
    avg = float(pd.to_numeric(subset['_prob'], errors='coerce').mean())
    gap = actual - avg
    verdict = 'reduce confidence' if gap < -0.04 else 'confidence supported' if gap > 0.04 else 'neutral'
    if LANG == 'es':
        verdict = {'reduce confidence': 'bajar confianza', 'confidence supported': 'confianza apoyada', 'neutral': 'neutral'}[verdict]
    return {'similar_rows': int(len(subset)), 'avg_predicted': round(avg, 4), 'actual_win_rate': round(actual, 4), 'calibration_gap': round(gap, 4), 'message': f'{len(subset)} similar finished rows. Avg predicted {avg * 100:.1f}%, actual {actual * 100:.1f}%, gap {gap * 100:.1f} pts. {verdict}.'}


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
cal = calibration_summary_local()
clv = clv_table()

cols = st.columns(10)
cols[0].metric('Rows' if LANG == 'en' else 'Filas', len(board))
cols[1].metric('Official-ready' if LANG == 'en' else 'Listas oficial', len(official_ready))
cols[2].metric('Shadow', len(shadow))
cols[3].metric('Review' if LANG == 'en' else 'Revisión', len(review))
cols[4].metric('Positive robust EV', accuracy.get('robust_positive_ev_rows', 0))
cols[5].metric('Lock candidates', accuracy.get('lock_candidate_rows', 0))
cols[6].metric('Avg odds score', accuracy.get('avg_odds_accuracy_score'))
cols[7].metric('Future rows', accuracy.get('future_rows', 0))
cols[8].metric('Calibration rows' if LANG == 'en' else 'Filas calib.', cal.get('resolved', 0))
cols[9].metric('CLV rows', len(clv))

st.subheader(t('route'))
for item in recommended_route(board, official_ready, review):
    st.write(f'- {item}')

options = [f"{row.get('prediction', 'Pick')} — {row.get('event', 'Event')}" for row in board.to_dict(orient='records')]
selected_label = st.selectbox('Selected game' if LANG == 'en' else 'Juego seleccionado', options)
selected = board.iloc[options.index(selected_label)].to_dict()

tabs = st.tabs([t('card'), t('explain'), t('board'), t('line'), t('ask'), t('review'), t('shadow'), t('official'), t('client'), t('calibration'), t('clv'), t('confidence'), t('memory'), t('report'), t('tools')])
with tabs[0]:
    st.markdown(selected.get('game_intelligence_card', 'No card available.'))
with tabs[1]:
    st.markdown(pick_explanation(selected))
    st.markdown(review_explanation(selected))
with tabs[2]:
    columns = display_columns(board)
    st.dataframe(board[columns] if columns else board, use_container_width=True, hide_index=True)
with tabs[3]:
    st.dataframe(line_shop_table(selected), use_container_width=True, hide_index=True)
with tabs[4]:
    question = st.text_input(t('question'), placeholder='What odds do I need? Why is this not ready? What is the next step?')
    st.write(agent_answer(selected, question))
with tabs[5]:
    st.dataframe(review, use_container_width=True, hide_index=True)
with tabs[6]:
    st.dataframe(shadow, use_container_width=True, hide_index=True)
    st.download_button(t('download_shadow'), shadow.to_csv(index=False), file_name='command_center_shadow_review.csv', mime='text/csv')
with tabs[7]:
    st.dataframe(official_preview, use_container_width=True, hide_index=True)
    st.caption(t('official_caption'))
with tabs[8]:
    client = client_view(board)
    st.dataframe(client, use_container_width=True, hide_index=True)
    st.download_button(t('download_client'), client.to_csv(index=False), file_name='command_center_client_view.csv', mime='text/csv')
with tabs[9]:
    st.json(cal)
    st.dataframe(calibration_table(), use_container_width=True, hide_index=True)
with tabs[10]:
    st.dataframe(clv, use_container_width=True, hide_index=True)
with tabs[11]:
    st.markdown(confidence_explanation(selected))
with tabs[12]:
    st.json(memory_influence(selected))
with tabs[13]:
    report = operator_daily_report(board)
    st.text_area(t('report'), value=report, height=420)
    st.download_button(t('download_report'), report, file_name='command_center_daily_report.md', mime='text/markdown')
with tabs[14]:
    st.dataframe(pd.DataFrame(page_rows()), use_container_width=True, hide_index=True)
    st.subheader(t('session_handoff'))
    st.dataframe(session_state_summary(), use_container_width=True, hide_index=True)
    st.subheader(t('workflow'))
    st.dataframe(pd.DataFrame({'step': range(1, len(WORKFLOW) + 1), 'tool': WORKFLOW}), use_container_width=True, hide_index=True)

st.download_button(t('download_full'), board.to_csv(index=False), file_name='command_center_board.csv', mime='text/csv')
