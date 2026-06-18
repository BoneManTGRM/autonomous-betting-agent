from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

APP_TAGLINE = 'Powered by Reparodynamics'
TOOLS: tuple[tuple[str, str], ...] = (
    ('Signal Board', 'pages/signal_board.py'),
    ('Pro Predictor', 'pages/pro_predictor.py'),
    ('Simulation Lab', 'pages/simulation_lab.py'),
    ('Threshold Optimizer', 'pages/threshold_optimizer.py'),
    ('What Are the Odds', 'pages/what_are_the_odds.py'),
    ('Odds Lock Pro', 'pages/odds_lock_pro.py'),
    ('Public Proof Dashboard', 'pages/public_proof_dashboard.py'),
    ('Learning Memory', 'pages/learn_memory.py'),
)
SIDEBAR_CSS = '''
<style>
section[data-testid="stSidebar"] a[href*="pages/"] {
  display:block; padding:.62rem .82rem; border-radius:.75rem; margin:.18rem 0;
  text-decoration:none!important; font-weight:650;
}
section[data-testid="stSidebar"] a[href*="pages/"]:hover { background:rgba(255,255,255,.10); }
</style>
'''


def normal_language(value: object) -> str:
    text = str(value or '').lower()
    return 'Español' if text.startswith('es') or 'español' in text or 'espanol' in text else 'English'


def sync_language(st_module: Any, value: object) -> str:
    lang = normal_language(value)
    for key in ('global_language', 'app_language'):
        try:
            st_module.session_state[key] = lang
        except Exception:
            pass
    return lang


def is_language_widget(label: Any, options: Any) -> bool:
    try:
        opts = list(options)
    except Exception:
        return False
    text = str(label or '').lower()
    return 'English' in opts and 'Español' in opts and ('language' in text or 'idioma' in text)


def inject_sidebar_css(st_module: Any) -> None:
    try:
        st_module.sidebar.markdown(SIDEBAR_CSS, unsafe_allow_html=True)
    except Exception:
        pass


def render_sidebar_brand(st_module: Any) -> None:
    if st_module.session_state.get('_aba_sidebar_legacy_brand_rendered'):
        return
    st_module.session_state['_aba_sidebar_legacy_brand_rendered'] = True
    st_module.sidebar.markdown('### :green[ABA] Signal :red[Pro]')
    st_module.sidebar.caption(APP_TAGLINE)


def render_curated_sidebar(st_module: Any, language: object = 'English') -> None:
    if st_module.session_state.get('_aba_sidebar_legacy_tools_rendered'):
        return
    st_module.session_state['_aba_sidebar_legacy_tools_rendered'] = True
    inject_sidebar_css(st_module)
    st_module.sidebar.markdown('---')
    render_sidebar_brand(st_module)
    st_module.sidebar.markdown('---')
    st_module.sidebar.markdown('### Tools')
    for label, path in TOOLS:
        try:
            st_module.sidebar.page_link(path, label=label)
        except Exception:
            st_module.sidebar.caption(label)


def sidebar_language_selector(st_module: Any, *, key: str, default: str = 'English') -> str:
    try:
        value = st_module.session_state.get(key, st_module.session_state.get('global_language', default))
    except Exception:
        value = default
    return 'es' if normal_language(value) == 'Español' else 'en'


def render_tool_sidebar(page_key: str, language: str = 'English') -> None:
    render_curated_sidebar(st, language)


def install_sidebar_tools() -> None:
    return None


def session_state_summary() -> pd.DataFrame:
    return pd.DataFrame()


def proof_sidebar_snapshot() -> dict[str, int]:
    return {'pro_predictor_rows': 0, 'high_confidence_rows': 0, 'locked_rows': 0}
