from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.agent_decision_engine import build_agent_decisions
from autonomous_betting_agent.four_tool_orchestrator import page_health, page_health_frame

st.set_page_config(page_title='Ultra 80 Profit Mode', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='ultra80_profit_mode_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Ultra 80 Profit + Max Volume Mode',
        'caption': 'Builds the strict 80%+ profitable proof list, then adds the largest safe reserve list without mixing the tiers.',
        'source': 'Prediction source', 'session': 'Use latest Pro Predictor session', 'upload': 'Upload Pro Predictor CSV', 'upload_label': 'Upload CSV',
        'run': 'Build max-volume shortlist', 'no_rows': 'No rows available. Run Pro Predictor first or upload a CSV.',
        'no_pass': 'No rows passed the selected tier. That is normal when the filters are strict.',
        'all_rows': 'All reviewed rows', 'strict_rows': 'A — Strict Ultra 80 proof', 'max_rows_tab': 'B — Max profitable volume', 'reserve_rows': 'C — Rescan/watch reserve', 'selected_rows': 'Selected handoff',
        'download': 'Download selected CSV', 'download_strict': 'Download strict Ultra 80 CSV', 'download_all': 'Download reviewed CSV',
        'reviewed': 'Rows reviewed', 'strict': 'Strict Ultra 80', 'max_profit': 'Max-profit volume', 'reserve': 'Reserve/watch', 'handoff': 'Handoff rows', 'avg_prob': 'Avg model probability', 'avg_ev': 'Avg EV/unit', 'avg_profit80': 'Avg profit at 80%', 'next': 'Next action',
        'rules': 'Tier rules',
        'rule_text': 'A = official proof tier. Requires 80%+ probability, profitable odds at 80%, positive EV, strong edge, 6+ books, API coverage, no draw, clean timing, no bad line movement, and no negative memory pattern. B = more volume but still profitable-leaning. C = close rows to rescan or manually review. Do not mix B/C into proof unless they are locked and tracked separately.',
        'proof': 'Lock before start time. Track A, B, and C separately. A is the only 80% proof tier.',
        'handoff_mode': 'Handoff mode', 'strict_only': 'A only — strict proof', 'max_volume': 'A+B — max profitable volume', 'research_volume': 'A+B+C — research/rescan volume',
        'saved': 'Selected rows saved as the active handoff list for Odds Lock Pro.',
    },
    'es': {
        'title': 'Modo Ultra 80 Rentable + Volumen Máximo',
        'caption': 'Crea la lista estricta de prueba 80%+ rentable y luego agrega la mayor lista de reserva segura sin mezclar los niveles.',
        'source': 'Fuente de predicciones', 'session': 'Usar última sesión de Predictor Pro', 'upload': 'Subir CSV de Predictor Pro', 'upload_label': 'Subir CSV',
        'run': 'Crear lista de volumen máximo', 'no_rows': 'No hay filas disponibles. Ejecuta Predictor Pro primero o sube un CSV.',
        'no_pass': 'Ninguna fila pasó el nivel seleccionado. Eso es normal con filtros estrictos.',
        'all_rows': 'Todas las filas revisadas', 'strict_rows': 'A — Prueba Ultra 80 estricta', 'max_rows_tab': 'B — Volumen rentable máximo', 'reserve_rows': 'C — Reserva para reescanear/vigilar', 'selected_rows': 'Traspaso seleccionado',
        'download': 'Descargar CSV seleccionado', 'download_strict': 'Descargar CSV Ultra 80 estricto', 'download_all': 'Descargar CSV revisado',
        'reviewed': 'Filas revisadas', 'strict': 'Ultra 80 estricto', 'max_profit': 'Volumen rentable', 'reserve': 'Reserva/vigilar', 'handoff': 'Filas traspaso', 'avg_prob': 'Probabilidad promedio', 'avg_ev': 'EV promedio/unidad', 'avg_profit80': 'Ganancia promedio al 80%', 'next': 'Siguiente acción',
        'rules': 'Reglas por nivel',
        'rule_text': 'A = nivel oficial de prueba. Requiere 80%+ probabilidad, cuotas rentables al 80%, EV positivo, ventaja fuerte, 6+ casas, cobertura API, sin empates, timing limpio, sin mal movimiento de línea y sin patrón negativo de memoria. B = más volumen pero todavía con sesgo rentable. C = filas cercanas para reescanear o revisar manualmente. No mezcles B/C como prueba si no están bloqueadas y separadas.',
        'proof': 'Bloquear antes del inicio. Rastrear A, B y C por separado. A es el único nivel de prueba 80%.',
        'handoff_mode': 'Modo de traspaso', 'strict_only': 'Solo A — prueba estricta', 'max_volume': 'A+B — volumen rentable máximo', 'research_volume': 'A+B+C — volumen de investigación/reescanear',
        'saved': 'Filas seleccionadas guardadas como lista activa para Odds Lock Pro.',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def pct(value: Any) -> str:
    number = pd.to_numeric(pd.Series([value]), errors='coerce').iloc[0]
    if pd.isna(number):
        return 'N/A'
    return f'{float(number) * 100:.1f}%'


def load_session_frame() -> pd.DataFrame:
    for key in ('pro_predictor_all_rows', 'pro_predictor_high_confidence_rows', 'pro_predictor_latest_rows', 'ara_latest_predictions'):
        rows = st.session_state.get(key)
        if isinstance(rows, list) and rows:
            return pd.DataFrame(rows)
    return pd.DataFrame()


def clean_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(index=frame.index if frame is not None else None, dtype=float)
    values = pd.to_numeric(frame[column], errors='coerce')
    if 'prob' in column.lower() or column in {'ultra80_profit_at_80_percent', 'profit_at_80_percent', 'expected_value_per_unit', 'model_market_edge', 'pattern_ara_memory_signal'}:
        values = values.where(values <= 1.0, values / 100.0)
    return values


def text_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series('', index=frame.index if frame is not None else None, dtype=str)
    return frame[column].fillna('').astype(str).str.lower().str.strip()


def bool_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame is None or frame.empty or column not in frame.columns:
        return pd.Series(False, index=frame.index if frame is not None else None, dtype=bool)
    return text_series(frame, column).isin(['true', '1', 'yes', 'y', 'pass'])


def source_frame() -> tuple[pd.DataFrame, str]:
    choice = st.radio(t('source'), [t('session'), t('upload')], horizontal=True)
    if choice == t('upload'):
        upload = st.file_uploader(t('upload_label'), type=['csv'], key='ultra80_upload_csv')
        if upload is None:
            return pd.DataFrame(), 'upload'
        try:
            return pd.read_csv(upload), getattr(upload, 'name', 'uploaded_csv')
        except Exception as exc:
            st.error(str(exc))
            return pd.DataFrame(), 'upload_error'
    return load_session_frame(), 'session'


def non_hard_blocked(frame: pd.DataFrame) -> pd.Series:
    reasons = text_series(frame, 'ultra80_reasons') + ' | ' + text_series(frame, 'decision_reasons')
    hard_tokens = (
        'historical_result_present',
        'bad_timing',
        'prediction_timestamp_not_before_start',
        'event_already_started_without_prediction_timestamp',
        'missing_event',
        'missing_prediction',
        'missing_model_probability',
        'missing_decimal_price',
        'blocks_draws',
        'negative_line_movement',
    )
    blocked = pd.Series(False, index=frame.index)
    for token in hard_tokens:
        blocked = blocked | reasons.str.contains(token, regex=False)
    return ~blocked


def build_tiers(reviewed: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if reviewed.empty:
        empty = pd.DataFrame()
        return empty, empty, empty
    strict_mask = bool_series(reviewed, 'ultra80_candidate')
    probability = clean_numeric(reviewed, 'model_probability_clean').fillna(clean_numeric(reviewed, 'model_probability'))
    ev = clean_numeric(reviewed, 'expected_value_per_unit')
    profit80 = clean_numeric(reviewed, 'ultra80_profit_at_80_percent').fillna(clean_numeric(reviewed, 'profit_at_80_percent'))
    edge = clean_numeric(reviewed, 'model_market_edge')
    books = clean_numeric(reviewed, 'bookmaker_count').fillna(clean_numeric(reviewed, 'books'))
    api_coverage = clean_numeric(reviewed, 'api_coverage_score')
    agent_score = clean_numeric(reviewed, 'agent_score')
    pattern_signal = clean_numeric(reviewed, 'pattern_ara_memory_signal').fillna(clean_numeric(reviewed, 'ara_memory_signal')).fillna(0.0)
    draw = bool_series(reviewed, 'is_draw_prediction')
    safe_timing = non_hard_blocked(reviewed)

    max_mask = (
        ~strict_mask
        & safe_timing
        & ~draw
        & probability.ge(0.76).fillna(False)
        & profit80.gt(0.0).fillna(False)
        & ev.ge(0.005).fillna(False)
        & edge.ge(0.04).fillna(False)
        & books.ge(4).fillna(False)
        & api_coverage.ge(0.50).fillna(False)
        & agent_score.ge(60).fillna(False)
        & pattern_signal.ge(-0.02).fillna(False)
    )

    reserve_mask = (
        ~strict_mask
        & ~max_mask
        & safe_timing
        & ~draw
        & probability.ge(0.72).fillna(False)
        & profit80.gt(0.0).fillna(False)
        & edge.ge(0.02).fillna(False)
        & books.ge(3).fillna(False)
        & pattern_signal.ge(-0.035).fillna(False)
    )

    sort_cols = [col for col in ['agent_score', 'model_probability_clean', 'expected_value_per_unit', 'ultra80_profit_at_80_percent', 'model_market_edge'] if col in reviewed.columns]

    def finish(frame: pd.DataFrame, tier: str) -> pd.DataFrame:
        if frame.empty:
            return frame.copy()
        out = frame.copy()
        out.insert(0, 'volume_tier', tier)
        if sort_cols:
            out = out.sort_values(sort_cols, ascending=False, na_position='last')
        return out.reset_index(drop=True)

    return finish(reviewed[strict_mask], 'A_strict_ultra80_proof'), finish(reviewed[max_mask], 'B_max_profitable_volume'), finish(reviewed[reserve_mask], 'C_rescan_watch_reserve')


def selected_handoff(strict: pd.DataFrame, max_profit: pd.DataFrame, reserve: pd.DataFrame, mode: str) -> pd.DataFrame:
    if mode == t('strict_only'):
        return strict.copy()
    if mode == t('max_volume'):
        return pd.concat([strict, max_profit], ignore_index=True)
    return pd.concat([strict, max_profit, reserve], ignore_index=True)


def display_columns(frame: pd.DataFrame) -> list[str]:
    return [
        col for col in [
            'volume_tier', 'event', 'sport', 'market_type', 'prediction', 'model_probability_clean', 'decimal_price',
            'market_implied_probability', 'model_market_edge', 'expected_value_per_unit', 'ultra80_profit_at_80_percent',
            'bookmaker_count', 'api_coverage_score', 'pattern_ara_memory_signal', 'line_value_signal', 'agent_score',
            'recommended_stake_units', 'ultra80_signals', 'ultra80_reasons', 'decision_reasons'
        ] if col in frame.columns
    ]


def show_table(frame: pd.DataFrame, label: str, filename: str) -> None:
    if frame.empty:
        st.info(t('no_pass'))
        return
    cols = display_columns(frame)
    st.dataframe(frame[cols] if cols else frame, use_container_width=True, hide_index=True)
    st.download_button(label, frame.to_csv(index=False), file_name=filename, mime='text/csv')


st.title(t('title'))
st.caption(t('caption'))
with st.expander(t('rules'), expanded=True):
    st.write(t('rule_text'))
    st.warning(t('proof'))

frame, source = source_frame()
handoff_mode = st.selectbox(t('handoff_mode'), [t('max_volume'), t('strict_only'), t('research_volume')], index=0)

if st.button(t('run'), type='primary', use_container_width=True):
    if frame.empty:
        st.info(t('no_rows'))
        st.stop()

    reviewed = build_agent_decisions(frame)
    strict, max_profit, reserve = build_tiers(reviewed)
    handoff = selected_handoff(strict, max_profit, reserve, handoff_mode)

    if not handoff.empty:
        st.session_state['ultra80_profit_mode_rows'] = strict.to_dict('records')
        st.session_state['ultra80_max_volume_rows'] = max_profit.to_dict('records')
        st.session_state['ultra80_reserve_rows'] = reserve.to_dict('records')
        st.session_state['pro_predictor_latest_rows'] = handoff.to_dict('records')
        st.session_state['ara_latest_predictions'] = handoff.to_dict('records')
        st.session_state['ara_latest_predictions_source'] = f'Ultra 80 Profit Mode — {handoff_mode}'
        st.success(t('saved'))
    else:
        st.warning(t('no_pass'))

    metrics = st.columns(8)
    metrics[0].metric(t('reviewed'), len(reviewed))
    metrics[1].metric(t('strict'), len(strict))
    metrics[2].metric(t('max_profit'), len(max_profit))
    metrics[3].metric(t('reserve'), len(reserve))
    metrics[4].metric(t('handoff'), len(handoff))
    metrics[5].metric(t('avg_prob'), pct(clean_numeric(handoff, 'model_probability_clean').mean()) if not handoff.empty else 'N/A')
    metrics[6].metric(t('avg_ev'), pct(clean_numeric(handoff, 'expected_value_per_unit').mean()) if not handoff.empty else 'N/A')
    metrics[7].metric(t('avg_profit80'), pct(clean_numeric(handoff, 'ultra80_profit_at_80_percent').mean()) if not handoff.empty else 'N/A')

    health = page_health(handoff if not handoff.empty else reviewed, page='ultra80_profit_mode')
    st.metric(t('next'), health.get('next_action', 'review'))

    tabs = st.tabs([t('selected_rows'), t('strict_rows'), t('max_rows_tab'), t('reserve_rows'), t('all_rows')])
    with tabs[0]:
        show_table(handoff, t('download'), 'ultra80_selected_handoff.csv')
        if not handoff.empty:
            st.subheader('Handoff health')
            st.dataframe(page_health_frame(handoff, page='ultra80_profit_mode'), use_container_width=True, hide_index=True)
    with tabs[1]:
        show_table(strict, t('download_strict'), 'ultra80_strict_proof.csv')
    with tabs[2]:
        show_table(max_profit, 'Download max-volume CSV' if LANG == 'en' else 'Descargar CSV volumen máximo', 'ultra80_max_profitable_volume.csv')
    with tabs[3]:
        show_table(reserve, 'Download reserve CSV' if LANG == 'en' else 'Descargar CSV reserva', 'ultra80_rescan_watch_reserve.csv')
    with tabs[4]:
        show_table(reviewed, t('download_all'), 'ultra80_reviewed_all_rows.csv')
