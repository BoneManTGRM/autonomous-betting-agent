from __future__ import annotations

from io import StringIO

import pandas as pd
import streamlit as st

from autonomous_betting_agent.agent_decision_engine import agent_decision_summary, build_agent_decisions, lock_ready_candidates, playable_candidates
from autonomous_betting_agent.clv_intelligence import build_clv_intelligence, clv_by_segment, clv_summary
from autonomous_betting_agent.mobile_report import compact_report_frame
from autonomous_betting_agent.odds_breakdown import build_odds_breakdown
from autonomous_betting_agent.performance_segments import build_segment_frame, top_segments
from autonomous_betting_agent.row_normalizer import normalize_frame

st.set_page_config(page_title='Market Finder Pro', layout='wide')
LANG = 'es' if st.sidebar.selectbox('Language / Idioma', ['English', 'Español'], key='market_finder_pro_language') == 'Español' else 'en'

TEXT = {
    'en': {
        'title': 'Market Finder Pro',
        'caption': 'One consolidated market/value finder for Scanner Pro, Pro Predictor, odds exports, props, and graded result CSVs.',
        'info': 'Use this instead of older market finder pages. It combines odds breakdown, agent decisions, value candidates, CLV, and segment analysis.',
        'upload': 'Upload CSV file(s)',
        'paste': 'Or paste CSV text',
        'use_session': 'Use latest Scanner Pro / Pro Predictor session rows',
        'waiting': 'Upload CSVs, paste CSV text, or use latest session rows.',
        'min_edge': 'Minimum model-vs-market edge',
        'strong_edge': 'Strong edge threshold',
        'source': 'Source',
        'rows': 'Rows',
        'playable': 'Playable',
        'lock_ready': 'Lock ready',
        'watch': 'Watch only',
        'review': 'Review needed',
        'clv_ready': 'CLV ready',
        'beat_close': 'Beat-close rate',
        'all_decisions': 'All decisions',
        'playable_candidates': 'Playable candidates',
        'lock_candidates': 'Lock-ready candidates',
        'odds_breakdown': 'Odds breakdown',
        'segments': 'Segments',
        'clv': 'CLV',
        'exports': 'Exports',
        'download_decisions': 'Download all market finder decisions',
        'download_playable': 'Download playable candidates',
        'download_lock_ready': 'Download lock-ready candidates',
        'download_breakdown': 'Download odds breakdown',
        'download_segments': 'Download segments',
        'download_clv': 'Download CLV intelligence',
    },
    'es': {
        'title': 'Market Finder Pro',
        'caption': 'Buscador único de mercados y valor para Scanner Pro, Pro Predictor, exportaciones de cuotas, props y CSVs con resultados calificados.',
        'info': 'Usa esta página en lugar de las páginas antiguas de búsqueda de mercados. Combina desglose de cuotas, decisiones del agente, candidatos de valor, CLV y análisis por segmento.',
        'upload': 'Subir archivo(s) CSV',
        'paste': 'O pegar texto CSV',
        'use_session': 'Usar las filas más recientes de Scanner Pro / Pro Predictor',
        'waiting': 'Sube CSVs, pega texto CSV o usa las filas recientes de la sesión.',
        'min_edge': 'Ventaja mínima modelo-vs-mercado',
        'strong_edge': 'Umbral de ventaja fuerte',
        'source': 'Fuente',
        'rows': 'Filas',
        'playable': 'Jugables',
        'lock_ready': 'Listas para bloquear',
        'watch': 'Solo vigilar',
        'review': 'Revisar',
        'clv_ready': 'CLV listo',
        'beat_close': 'Tasa de superar el cierre',
        'all_decisions': 'Todas las decisiones',
        'playable_candidates': 'Candidatos jugables',
        'lock_candidates': 'Candidatos listos para bloquear',
        'odds_breakdown': 'Desglose de cuotas',
        'segments': 'Segmentos',
        'clv': 'CLV',
        'exports': 'Exportaciones',
        'download_decisions': 'Descargar todas las decisiones',
        'download_playable': 'Descargar candidatos jugables',
        'download_lock_ready': 'Descargar candidatos listos para bloquear',
        'download_breakdown': 'Descargar desglose de cuotas',
        'download_segments': 'Descargar segmentos',
        'download_clv': 'Descargar inteligencia CLV',
    },
}


def t(key: str) -> str:
    return TEXT[LANG].get(key, TEXT['en'].get(key, key))


def read_inputs() -> tuple[str, pd.DataFrame]:
    use_session = st.checkbox(t('use_session'), value=bool(st.session_state.get('scanner_pro_latest_rows') or st.session_state.get('ara_latest_predictions')))
    frames: list[pd.DataFrame] = []
    names: list[str] = []
    if use_session:
        session_rows = st.session_state.get('scanner_pro_latest_rows') or st.session_state.get('ara_latest_predictions') or []
        if session_rows:
            frames.append(pd.DataFrame(session_rows))
            names.append('session_rows')
    uploads = st.file_uploader(t('upload'), type=['csv'], accept_multiple_files=True)
    pasted = st.text_area(t('paste'), height=120)
    if uploads:
        for upload in uploads:
            try:
                frame = pd.read_csv(upload)
                frame['source_file'] = upload.name
                frames.append(frame)
                names.append(upload.name)
            except Exception as exc:
                st.warning(f'Could not read {upload.name}: {exc}')
    if pasted.strip():
        try:
            frame = pd.read_csv(StringIO(pasted.strip()))
            frame['source_file'] = 'pasted_csv'
            frames.append(frame)
            names.append('pasted_csv')
        except Exception as exc:
            st.warning(f'Could not read pasted CSV: {exc}')
    if not frames:
        return '', pd.DataFrame()
    return ', '.join(names), pd.concat(frames, ignore_index=True, sort=False)


st.title(t('title'))
st.caption(t('caption'))
st.info(t('info'))
source, raw = read_inputs()
if raw.empty:
    st.warning(t('waiting'))
    st.stop()

min_edge = st.slider(t('min_edge'), min_value=0.0, max_value=0.20, value=0.035, step=0.005)
strong_edge = st.slider(t('strong_edge'), min_value=0.0, max_value=0.30, value=0.075, step=0.005)
normalized = normalize_frame(raw)
decisions = build_agent_decisions(normalized, min_edge=float(min_edge), strong_edge=float(strong_edge))
plays = playable_candidates(normalized, min_edge=float(min_edge), strong_edge=float(strong_edge))
lock_ready = lock_ready_candidates(normalized, min_edge=float(min_edge), strong_edge=float(strong_edge))
summary = agent_decision_summary(normalized, min_edge=float(min_edge), strong_edge=float(strong_edge))
segments = build_segment_frame(normalized)
top = top_segments(normalized, min_resolved=1, limit=30)
clv = build_clv_intelligence(normalized)
clv_stats = clv_summary(normalized)
clv_sport = clv_by_segment(normalized, 'sport')
try:
    odds_main, odds_props, odds_diag = build_odds_breakdown(raw)
except Exception:
    odds_main, odds_props, odds_diag = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

st.caption(f"{t('source')}: {source}")
cols = st.columns(7)
cols[0].metric(t('rows'), len(normalized))
cols[1].metric(t('playable'), summary['play_strong'] + summary['play_small'])
cols[2].metric(t('lock_ready'), len(lock_ready))
cols[3].metric(t('watch'), summary['watch_only'])
cols[4].metric(t('review'), summary['review_needed'])
cols[5].metric(t('clv_ready'), clv_stats['ready'])
cols[6].metric(t('beat_close'), 'N/A' if clv_stats['beat_close_rate'] is None else f"{clv_stats['beat_close_rate']:.1%}")

tabs = st.tabs([t('all_decisions'), t('playable_candidates'), t('lock_candidates'), t('odds_breakdown'), t('segments'), t('clv'), t('exports')])
with tabs[0]:
    st.dataframe(decisions.head(500), use_container_width=True, hide_index=True)
with tabs[1]:
    st.dataframe(plays.head(300), use_container_width=True, hide_index=True)
with tabs[2]:
    st.dataframe(lock_ready.head(300), use_container_width=True, hide_index=True)
with tabs[3]:
    st.dataframe(compact_report_frame(odds_main).head(500) if not odds_main.empty else odds_main, use_container_width=True, hide_index=True)
    if not odds_props.empty:
        st.subheader('Props / Scores' if LANG == 'en' else 'Props / Marcadores')
        st.dataframe(odds_props.head(300), use_container_width=True, hide_index=True)
with tabs[4]:
    st.subheader('Top segments' if LANG == 'en' else 'Mejores segmentos')
    st.dataframe(top, use_container_width=True, hide_index=True)
    st.subheader('All segments' if LANG == 'en' else 'Todos los segmentos')
    st.dataframe(segments, use_container_width=True, hide_index=True)
with tabs[5]:
    st.json(clv_stats)
    st.dataframe(clv.head(500), use_container_width=True, hide_index=True)
    st.subheader('CLV by sport' if LANG == 'en' else 'CLV por deporte')
    st.dataframe(clv_sport, use_container_width=True, hide_index=True)
with tabs[6]:
    st.download_button(t('download_decisions'), decisions.to_csv(index=False), file_name='market_finder_pro_decisions.csv', mime='text/csv')
    st.download_button(t('download_playable'), plays.to_csv(index=False), file_name='market_finder_pro_playable.csv', mime='text/csv')
    st.download_button(t('download_lock_ready'), lock_ready.to_csv(index=False), file_name='market_finder_pro_lock_ready.csv', mime='text/csv')
    st.download_button(t('download_breakdown'), odds_main.to_csv(index=False), file_name='market_finder_pro_odds_breakdown.csv', mime='text/csv')
    st.download_button(t('download_segments'), segments.to_csv(index=False), file_name='market_finder_pro_segments.csv', mime='text/csv')
    st.download_button(t('download_clv'), clv.to_csv(index=False), file_name='market_finder_pro_clv.csv', mime='text/csv')
