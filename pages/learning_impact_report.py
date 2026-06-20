from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from autonomous_betting_agent.adaptive_learning import threshold_suggestions
from autonomous_betting_agent.sidebar_nav import render_app_sidebar

REPO_ROOT = Path(__file__).resolve().parents[1]
MEMORY_BANK_PATH = REPO_ROOT / 'data' / 'learning_memory_bank.json'

st.set_page_config(page_title='Learning Impact Report', layout='wide')
LANG = render_app_sidebar('learning_impact_report', language_key='learning_impact_report_language', selector='radio')

TEXT = {
    'en': {
        'title': 'Learning Impact Report',
        'caption': 'Shows whether the memory is useful enough to affect future ranking, staking, and pattern blocking.',
        'missing': 'No learning_memory_bank.json found yet. Train Learning Memory first.',
        'summary': 'Memory summary',
        'suggestions': 'Automatic threshold suggestions',
        'leaderboards': 'Pattern leaderboards',
        'best_roi': 'Best ROI patterns',
        'worst_roi': 'Worst ROI / blocklist candidates',
        'best_hit': 'Best hit-rate patterns',
        'reliable': 'Most reliable patterns',
        'patterns': 'All learned patterns',
    },
    'es': {
        'title': 'Reporte de Impacto del Aprendizaje',
        'caption': 'Muestra si la memoria es útil para afectar ranking, staking y bloqueo de patrones.',
        'missing': 'No se encontró learning_memory_bank.json. Primero entrena Memoria de Aprendizaje.',
        'summary': 'Resumen de memoria',
        'suggestions': 'Sugerencias automáticas de umbrales',
        'leaderboards': 'Tablas de patrones',
        'best_roi': 'Mejores patrones por ROI',
        'worst_roi': 'Peores ROI / candidatos a bloquear',
        'best_hit': 'Mejores patrones por win rate',
        'reliable': 'Patrones más confiables',
        'patterns': 'Todos los patrones aprendidos',
    },
}


def t(key: str) -> str:
    return TEXT.get(LANG, TEXT['en']).get(key, TEXT['en'].get(key, key))


def load_bank() -> dict[str, Any]:
    try:
        return json.loads(MEMORY_BANK_PATH.read_text(encoding='utf-8'))
    except Exception:
        return {}


def show_frame(title: str, rows: list[dict[str, Any]]) -> None:
    st.subheader(title)
    if not rows:
        st.info('No rows yet.' if LANG == 'en' else 'Todavía no hay filas.')
        return
    frame = pd.DataFrame(rows)
    cols = [col for col in ['area', 'area_type', 'group_value', 'records', 'actual_hit_rate', 'roi', 'profit_units', 'avg_price', 'avg_clv_percent', 'beat_close_rate', 'smoothed_edge', 'reliability', 'action'] if col in frame.columns]
    st.dataframe(frame[cols] if cols else frame, use_container_width=True, hide_index=True)


st.title(t('title'))
st.caption(t('caption'))

bank = load_bank()
if not bank:
    st.warning(t('missing'))
    st.stop()

summary = bank.get('summary', {}) if isinstance(bank.get('summary'), dict) else {}
patterns = bank.get('patterns', []) if isinstance(bank.get('patterns'), list) else []
leaderboards = bank.get('pattern_leaderboards', {}) if isinstance(bank.get('pattern_leaderboards'), dict) else {}
suggestions = threshold_suggestions(MEMORY_BANK_PATH)

st.subheader(t('summary'))
cols = st.columns(6)
cols[0].metric('Rows', summary.get('rows_after_pruning', len(bank.get('compact_rows', []))))
cols[1].metric('Patterns', summary.get('patterns_saved', len(patterns)))
roi = summary.get('roi')
cols[2].metric('ROI', 'N/A' if roi is None else f'{float(roi) * 100:.2f}%')
cols[3].metric('Profit units', summary.get('profit_units', 'N/A'))
cols[4].metric('Health', summary.get('learning_health_score', 'N/A'))
cols[5].metric('Tier', str(summary.get('learning_health_tier', 'unknown')).replace('_', ' '))

st.subheader(t('suggestions'))
s1, s2, s3, s4 = st.columns(4)
s1.metric('Recommended learned score', suggestions.get('recommended_min_learned_score'))
s2.metric('Recommended min edge', suggestions.get('recommended_min_edge'))
s3.metric('Positive patterns', suggestions.get('positive_pattern_count'))
s4.metric('Negative patterns', suggestions.get('negative_pattern_count'))

left, right = st.columns(2)
with left:
    st.write('Preferred markets / patterns' if LANG == 'en' else 'Mercados / patrones preferidos')
    st.write(suggestions.get('preferred_markets') or [])
with right:
    st.write('Avoid / review patterns' if LANG == 'en' else 'Patrones a evitar / revisar')
    st.write(suggestions.get('avoid_patterns') or [])

st.subheader(t('leaderboards'))
show_frame(t('best_roi'), leaderboards.get('best_roi', []))
show_frame(t('worst_roi'), leaderboards.get('worst_roi', []))
show_frame(t('best_hit'), leaderboards.get('best_hit_rate', []))
show_frame(t('reliable'), leaderboards.get('most_reliable', []))

st.subheader(t('patterns'))
if patterns:
    st.dataframe(pd.DataFrame(patterns), use_container_width=True, hide_index=True)
else:
    st.info('No patterns yet.' if LANG == 'en' else 'Todavía no hay patrones.')
