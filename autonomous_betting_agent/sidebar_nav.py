from __future__ import annotations

import base64
import html
from typing import Any

APP_TAGLINE = 'Powered by Reparodynamics'
APP_TAGLINE_ES = 'Impulsado por Reparodynamics'
LANGUAGE_KEYS = ['global_language','signal_board_language','pro_predictor_language','threshold_optimizer_language','what_are_the_odds_language','what_are_the_odds_pro_language','odds_lock_pro_language','public_proof_dashboard_language','storage_diagnostics_language','learning_memory_language','learning_impact_report_language','simulation_lab_language','proof_control_center_language','reset_storage_language']
TOOLS: tuple[tuple[str, str, str], ...] = (
    ('Signal Board', 'Panel de Señales', 'pages/signal_board.py'),
    ('Pro Predictor', 'Predictor Pro', 'pages/pro_predictor_volume.py'),
    ('Simulation Lab', 'Laboratorio de Simulación', 'pages/simulation_lab.py'),
    ('Threshold Optimizer', 'Optimizador de Umbral', 'pages/threshold_optimizer.py'),
    ('What Are the Odds', 'Cuáles Son las Cuotas', 'pages/what_are_the_odds.py'),
    ('Odds Lock Pro', 'Bloqueo de Cuotas Pro', 'pages/odds_lock_pro.py'),
    ('Proof Control Center', 'Centro de Control de Prueba', 'pages/proof_control_center.py'),
    ('Public Proof Dashboard', 'Panel Público de Prueba', 'pages/public_proof_dashboard.py'),
    ('Storage Diagnostics', 'Diagnóstico de Almacenamiento', 'pages/storage_diagnostics.py'),
    ('Reset Storage', 'Reiniciar almacenamiento', 'pages/reset_storage.py'),
    ('Learning Memory', 'Memoria de Aprendizaje', 'pages/learn_memory_safe.py'),
)
PRO_PREDICTOR_LARGE_LIST_70_DEFAULTS = {'baseline_accuracy_min_books': 1,'baseline_accuracy_min_model_prob': 0.58,'baseline_accuracy_min_edge': -0.03,'baseline_accuracy_strong_edge': 0.04,'baseline_accuracy_min_strength': 38.0,'baseline_accuracy_use_high_conf': True,'baseline_accuracy_max_high_conf': 700,'baseline_accuracy_min_high_prob': 0.58,'baseline_accuracy_min_high_edge': -0.03,'baseline_accuracy_min_high_strength': 38.0,'baseline_accuracy_min_high_agent': 35.0}
SIDEBAR_CSS = '''
<style>
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: 1.4rem; }
.aba-side-link { display: block; padding: .62rem .82rem; border-radius: .75rem; margin: .18rem 0; text-decoration: none !important; font-weight: 650; color: inherit !important; }
.aba-side-link:hover { background: rgba(255,255,255,.10); }
.aba-side-active { display: block; padding: .62rem .82rem; border-radius: .75rem; margin: .18rem 0; font-weight: 800; background: rgba(255,255,255,.10); }
.aba-sidebar-title { font-size: 1.45rem; line-height: 1.2; font-weight: 850; margin: .35rem 0 .25rem 0; background: linear-gradient(90deg, #f6d365 0%, #fda085 40%, #70e1f5 100%); -webkit-background-clip: text; background-clip: text; color: transparent; }
.aba-sidebar-tagline { color: rgba(255,255,255,.62); margin-bottom: 1rem; }
.aba-lang-row { display:flex; gap:.45rem; margin:.45rem 0 .75rem 0; }
.aba-lang-pill { flex:1; text-align:center; padding:.45rem .55rem; border-radius:999px; border:1px solid rgba(255,255,255,.25); text-decoration:none!important; color:inherit!important; font-weight:700; }
.aba-lang-pill-active { background: rgba(255,255,255,.18); border-color: rgba(255,255,255,.55); }
.aba-safe-download { display:inline-block; padding:.65rem 1rem; border-radius:.7rem; background:#ef5350; color:#fff!important; text-decoration:none!important; font-weight:700; margin:.35rem 0; }
</style>
'''


def normalize_language(value: Any) -> str:
    text = str(value or '').strip().lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'es'
    return 'en'


def _query_language(st: Any) -> str | None:
    try:
        value = st.query_params.get('lang')
    except Exception:
        return None
    if isinstance(value, list):
        value = value[0] if value else None
    if str(value or '').lower() in {'en', 'es'}:
        return str(value).lower()
    return None


def _language_label(value: Any) -> str:
    return 'Español' if normalize_language(value) == 'es' else 'English'


def _current_language(st: Any) -> str:
    query_lang = _query_language(st)
    if query_lang:
        return 'Español' if query_lang == 'es' else 'English'
    value = st.session_state.get('global_language')
    if value in ('English', 'Español'):
        return value
    for key in LANGUAGE_KEYS:
        value = st.session_state.get(key)
        if value in ('English', 'Español'):
            return value
    return 'English'


def _label(item: tuple[str, str, str], language: str) -> str:
    return item[1] if normalize_language(language) == 'es' else item[0]


def _page_href(path: str, lang_code: str) -> str:
    return f'/{path}?lang={lang_code}'


def render_app_sidebar(current_page: str, *, language_key: str = 'global_language', selector: str = 'radio') -> str:
    import streamlit as st
    language = _language_label(_current_language(st))
    lang_code = normalize_language(language)
    try:
        st.query_params['lang'] = lang_code
    except Exception:
        pass
    try:
        st.session_state['global_language'] = language
    except Exception:
        pass
    with st.sidebar:
        st.markdown(SIDEBAR_CSS, unsafe_allow_html=True)
        st.markdown('<div class="aba-sidebar-title">ABA Signal Pro</div>', unsafe_allow_html=True)
        tagline = APP_TAGLINE if language == 'English' else APP_TAGLINE_ES
        st.markdown(f'<div class="aba-sidebar-tagline">{html.escape(tagline)}</div>', unsafe_allow_html=True)
        en_class = 'aba-lang-pill aba-lang-pill-active' if lang_code == 'en' else 'aba-lang-pill'
        es_class = 'aba-lang-pill aba-lang-pill-active' if lang_code == 'es' else 'aba-lang-pill'
        st.markdown(f'<div class="aba-lang-row"><a class="{en_class}" href="?lang=en">English</a><a class="{es_class}" href="?lang=es">Español</a></div>', unsafe_allow_html=True)
        st.markdown('---')
        for item in TOOLS:
            label = _label(item, language)
            path = item[2]
            safe_label = html.escape(label)
            if current_page and current_page in path:
                st.markdown(f'<span class="aba-side-active">● {safe_label}</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<a class="aba-side-link" href="{html.escape(_page_href(path, lang_code))}">{safe_label}</a>', unsafe_allow_html=True)
    return lang_code


def safe_csv_download(label: str, csv_text: str, filename: str) -> str:
    payload = base64.b64encode(str(csv_text or '').encode('utf-8')).decode('ascii')
    return f'<a class="aba-safe-download" download="{html.escape(filename)}" href="data:text/csv;base64,{payload}">{html.escape(label)}</a>'
