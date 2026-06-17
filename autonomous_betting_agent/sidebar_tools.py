from __future__ import annotations

from typing import Any

PAGES = (
    ('Pro Predictor', 'Predictor Pro', 'pages/pro_predictor.py'),
    ('Ultra 70 Profit Mode', 'Ultra 70 Profit Mode', 'pages/ultra80_profit_mode.py'),
    ('Simulation Lab', 'Laboratorio de Simulación', 'pages/simulation_lab.py'),
    ('Threshold Optimizer', 'Optimizador de Umbrales', 'pages/threshold_optimizer.py'),
    ('What Are the Odds', 'Cuotas y Valor', 'pages/what_are_the_odds.py'),
    ('Odds Lock Pro', 'Odds Lock Pro', 'pages/odds_lock_pro.py'),
    ('Public Proof Dashboard', 'Dashboard Público', 'pages/public_proof_dashboard.py'),
    ('Learning Memory', 'Memoria', 'pages/learn_memory.py'),
    ('Reset Lock File', 'Reiniciar Archivo', 'pages/reset_lock_file.py'),
)
LANG_KEYS = (
    'global_language', 'app_language', 'simulation_lab_language', 'pro_predictor_language',
    'ultra80_profit_mode_language', 'odds_lock_pro_language', 'public_proof_dashboard_language',
    'reset_lock_file_language', 'learn_memory_language', 'learning_memory_language',
    'threshold_optimizer_language', 'what_are_the_odds_language',
)
CSS = '''
<style>
[data-testid="collapsedControl"]{z-index:999999!important;}
@media(max-width:900px){
section[data-testid="stSidebar"]{width:min(86vw,360px)!important;min-width:min(86vw,360px)!important;max-width:min(86vw,360px)!important;box-shadow:0 0 0 9999px rgba(0,0,0,.32)!important;}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{padding:.75rem .9rem!important;}
.block-container{padding-left:.85rem!important;padding-right:.85rem!important;max-width:100vw!important;}
}
</style>
'''


def _lang(value: object) -> str:
    text = str(value or '').lower()
    return 'Español' if text.startswith('es') or 'español' in text or 'espanol' in text else 'English'


def _is_language(label: Any, options: Any) -> bool:
    try:
        opts = list(options)
    except Exception:
        return False
    label_text = str(label or '').lower()
    return 'English' in opts and 'Español' in opts and ('language' in label_text or 'idioma' in label_text)


def _sync_language(st: Any, value: object) -> str:
    language = _lang(value)
    for key in LANG_KEYS:
        try:
            st.session_state[key] = language
        except Exception:
            pass
    return language


def _render_brand(st: Any) -> None:
    if st.session_state.get('_aba_brand_curated_v1'):
        return
    st.session_state['_aba_brand_curated_v1'] = True
    with st.sidebar:
        st.markdown('### :green[ABA] Signal :red[Pro]')
        st.caption('Powered by Reparodynamics')
        st.markdown('---')


def _render_pages(st: Any, language: object) -> None:
    if st.session_state.get('_aba_pages_curated_v1'):
        return
    st.session_state['_aba_pages_curated_v1'] = True
    language = _lang(language)
    with st.sidebar:
        st.markdown('### Herramientas' if language == 'Español' else '### Pages')
        for english, spanish, path in PAGES:
            try:
                st.page_link(path, label=spanish if language == 'Español' else english)
            except Exception:
                st.caption(spanish if language == 'Español' else english)
        st.markdown('---')
        st.markdown('### Flujo' if language == 'Español' else '### Workflow')
        notes = (
            ('Predictor Pro → Máxima Confianza → Odds Lock Pro → Dashboard Público → Memoria.',
             'Odds Lock Pro bloquea picks con timestamp; Dashboard Público muestra ROI y resultados.')
            if language == 'Español'
            else
            ('Pro Predictor → Highest Confidence → Odds Lock Pro → Public Proof Dashboard → Learning Memory.',
             'Odds Lock Pro timestamps locked picks; Public Proof Dashboard shows ROI and results.')
        )
        for note in notes:
            st.caption(note)


def _render_after_language(st: Any, value: object) -> object:
    language = _sync_language(st, value)
    _render_pages(st, language)
    return value


def install_sidebar_tools() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return
    if getattr(st, '_aba_curated_sidebar_installed_v1', False):
        return
    st._aba_curated_sidebar_installed_v1 = True

    old_set_page_config = st.set_page_config
    old_markdown = st.markdown
    old_st_radio = st.radio
    old_st_selectbox = st.selectbox
    old_sidebar_radio = st.sidebar.radio
    old_sidebar_selectbox = st.sidebar.selectbox
    old_dg_radio = getattr(DeltaGenerator, 'radio', None)
    old_dg_selectbox = DeltaGenerator.selectbox

    def page_config(*args: Any, **kwargs: Any) -> Any:
        kwargs.setdefault('initial_sidebar_state', 'expanded')
        out = old_set_page_config(*args, **kwargs)
        try:
            old_markdown(CSS, unsafe_allow_html=True)
            _render_brand(st)
        except Exception:
            pass
        return out

    def sidebar_radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language(label, options):
            _render_brand(st)
            value = old_sidebar_radio(label, options, *args, **kwargs)
            return _render_after_language(st, value)
        return old_sidebar_radio(label, options, *args, **kwargs)

    def sidebar_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language(label, options):
            _render_brand(st)
            value = old_sidebar_selectbox(label, options, *args, **kwargs)
            return _render_after_language(st, value)
        return old_sidebar_selectbox(label, options, *args, **kwargs)

    def st_radio(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = old_st_radio(label, options, *args, **kwargs)
        if _is_language(label, options):
            _render_after_language(st, value)
        return value

    def st_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        value = old_st_selectbox(label, options, *args, **kwargs)
        if _is_language(label, options):
            _render_after_language(st, value)
        return value

    def dg_radio(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language(label, options):
            _render_brand(st)
            value = old_dg_radio(self, label, options, *args, **kwargs) if old_dg_radio else old_st_radio(label, options, *args, **kwargs)
            return _render_after_language(st, value)
        return old_dg_radio(self, label, options, *args, **kwargs) if old_dg_radio else old_st_radio(label, options, *args, **kwargs)

    def dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language(label, options):
            _render_brand(st)
            value = old_dg_selectbox(self, label, options, *args, **kwargs)
            return _render_after_language(st, value)
        return old_dg_selectbox(self, label, options, *args, **kwargs)

    st.set_page_config = page_config
    st.radio = st_radio
    st.selectbox = st_selectbox
    try:
        st.sidebar.radio = sidebar_radio
        st.sidebar.selectbox = sidebar_selectbox
    except Exception:
        pass
    if old_dg_radio:
        DeltaGenerator.radio = dg_radio
    DeltaGenerator.selectbox = dg_selectbox
