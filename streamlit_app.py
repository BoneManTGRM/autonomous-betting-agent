from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

try:
    from autonomous_betting_agent.memory_read_patch import install_memory_read_merge
except Exception:
    install_memory_read_merge = None  # type: ignore[assignment]

APP_NAME = 'ABA Signal Pro'
APP_TAGLINE = 'Powered by Reparodynamics'
APP_BUILD = 'hidden-nav-bottom-links-v3-radio-hook'
REPO_ROOT = Path(__file__).resolve().parent
REPO_MEMORY_PATH = REPO_ROOT / 'data' / 'ara_permanent_learning_memory.csv'

PAGE_LINKS = [
    ('Signal Board', 'pages/signal_board.py'),
    ('Pro Predictor', 'pages/pro_predictor.py'),
    ('Simulation Lab', 'pages/simulation_lab.py'),
    ('Threshold Optimizer', 'pages/threshold_optimizer.py'),
    ('What Are the Odds', 'pages/what_are_the_odds.py'),
    ('Odds Lock Pro', 'pages/odds_lock_pro.py'),
    ('Public Proof Dashboard', 'pages/public_proof_dashboard.py'),
    ('Learning Memory', 'pages/learn_memory.py'),
    ('Reset Lock File', 'pages/reset_lock_file.py'),
]


def mobile_safe_file_uploader(*args: Any, **kwargs: Any) -> Any:
    return st._aba_real_file_uploader(*args, **kwargs)


if not hasattr(st, '_aba_real_file_uploader'):
    st._aba_real_file_uploader = st.file_uploader
    st.file_uploader = mobile_safe_file_uploader

_REAL_SET_PAGE_CONFIG = st.set_page_config
_REAL_SET_PAGE_CONFIG(page_title=APP_NAME, layout='wide', initial_sidebar_state='expanded')

# Child pages call set_page_config. The shell owns page config to prevent conflicts.
st.set_page_config = lambda *args, **kwargs: None

st.sidebar.markdown('### :green[ABA] Signal :red[Pro]')
st.sidebar.caption(APP_TAGLINE)
st.sidebar.markdown('---')

CORE_PAGES = [st.Page(path, title=title) for title, path in PAGE_LINKS]


def is_language_widget(label: Any, options: Any) -> bool:
    try:
        values = list(options)
    except Exception:
        return False
    text = str(label or '').lower()
    return 'English' in values and 'Español' in values and ('language' in text or 'idioma' in text)


def render_bottom_sidebar_links() -> None:
    if st.session_state.get('_aba_bottom_links_rendered_v3'):
        return
    st.session_state['_aba_bottom_links_rendered_v3'] = True
    with st.sidebar:
        st.markdown('---')
        st.markdown('### Tools')
        for label, path in PAGE_LINKS:
            try:
                st.page_link(path, label=label)
            except Exception:
                st.caption(label)


def install_sidebar_language_hook() -> None:
    if getattr(st, '_aba_shell_sidebar_hook_v3', False):
        return
    real_radio = st.sidebar.radio
    real_selectbox = st.sidebar.selectbox

    def radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = real_radio(label, options, *args, **kwargs)
        if is_language_widget(label, options):
            render_bottom_sidebar_links()
        return value

    def selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = real_selectbox(label, options, *args, **kwargs)
        if is_language_widget(label, options):
            render_bottom_sidebar_links()
        return value

    st.sidebar.radio = radio
    st.sidebar.selectbox = selectbox
    st._aba_shell_sidebar_hook_v3 = True


def install_report_branding() -> None:
    try:
        from autonomous_betting_agent import odds_lock_tools
    except Exception:
        return
    original_daily_report = getattr(odds_lock_tools, 'daily_report', None)
    if not callable(original_daily_report) or getattr(original_daily_report, '_ara_brand_patched', False):
        return

    def branded_daily_report(*args: Any, **kwargs: Any) -> str:
        report = str(original_daily_report(*args, **kwargs) or '')
        if report.startswith(APP_NAME):
            return report
        return f'{APP_NAME}\n{APP_TAGLINE}\n\n{report}'

    branded_daily_report._ara_brand_patched = True  # type: ignore[attr-defined]
    odds_lock_tools.daily_report = branded_daily_report


install_sidebar_language_hook()
if install_memory_read_merge is not None:
    try:
        install_memory_read_merge(REPO_MEMORY_PATH)
    except Exception:
        pass
install_report_branding()

try:
    # Keep Streamlit's native page list hidden so links render below each page's language selector.
    current_page = st.navigation(CORE_PAGES, position='hidden')
    current_page.run()
    render_bottom_sidebar_links()
except AttributeError:
    import pages.pro_predictor  # noqa: F401,E402
    render_bottom_sidebar_links()
