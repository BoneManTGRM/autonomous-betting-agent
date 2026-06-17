from __future__ import annotations

from typing import Any

try:
    from autonomous_betting_agent.odds_input_normalizer import install_odds_breakdown_normalizer

    install_odds_breakdown_normalizer()
except Exception:
    pass

try:
    from autonomous_betting_agent.local_users import install_streamlit_local_user_selector

    install_streamlit_local_user_selector()
except Exception:
    pass


LANGUAGE_KEYS: tuple[str, ...] = (
    'global_language', 'app_language', 'simulation_lab_language', 'pro_predictor_language',
    'ultra80_profit_mode_language', 'odds_lock_pro_language', 'public_proof_dashboard_language',
    'reset_lock_file_language', 'learn_memory_language', 'learning_memory_language',
    'threshold_optimizer_language', 'what_are_the_odds_language',
)

PREDICTOR_FIRST_NAV_TOOLS: tuple[tuple[str, str, str], ...] = (
    ('Pro Predictor', 'Predictor Pro', 'pages/pro_predictor.py'),
    ('Ultra 70 Profit Mode', 'Ultra 70 Profit Mode', 'pages/ultra80_profit_mode.py'),
    ('Simulation Lab', 'Laboratorio de Simulación', 'pages/simulation_lab.py'),
    ('Odds Lock Pro', 'Bloqueo de Cuotas Pro', 'pages/odds_lock_pro.py'),
    ('Public Proof Dashboard', 'Dashboard Público de Prueba', 'pages/public_proof_dashboard.py'),
    ('Learning Memory', 'Memoria de Aprendizaje', 'pages/learn_memory.py'),
    ('What Are the Odds', 'Cuotas y Valor', 'pages/what_are_the_odds.py'),
    ('Threshold Optimizer', 'Optimizador de Umbrales', 'pages/threshold_optimizer.py'),
    ('Reset Lock File', 'Reiniciar Archivo de Bloqueo', 'pages/reset_lock_file.py'),
    ('Scanner Pro', 'Scanner Pro', 'pages/scanner_pro.py'),
)

NAV_NOTES_EN = (
    'Workflow: Pro Predictor → Ultra 70 Profit Mode → Simulation Lab → Odds Lock Pro → Public Proof Dashboard → Learning Memory.',
    'Start in Pro Predictor. Scanner Pro is optional legacy/research support and is no longer the main starting point.',
    'Use Reset Lock File only when clearing one test-window proof ledger without touching other windows.',
)
NAV_NOTES_ES = (
    'Flujo: Predictor Pro → Ultra 70 Profit Mode → Laboratorio de Simulación → Bloqueo de Cuotas Pro → Dashboard Público → Memoria.',
    'Empieza en Predictor Pro. Scanner Pro queda como soporte opcional/legacy, no como punto principal.',
    'Usa Reiniciar Archivo de Bloqueo solo para borrar un ledger de prueba sin tocar otros.',
)


def _normal_language(value: object) -> str:
    text = str(value or '').strip().lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'Español'
    return 'English'


def _is_language_selector(label: Any, options: Any) -> bool:
    try:
        opts = list(options)
    except Exception:
        return False
    text = str(label or '').lower()
    return ('language' in text or 'idioma' in text) and 'English' in opts and 'Español' in opts


def _sync_language_keys(st: Any, value: str, *, include_global: bool = False) -> None:
    for key in LANGUAGE_KEYS:
        if key == 'global_language' and not include_global:
            continue
        try:
            st.session_state[key] = value
        except Exception:
            pass


def _install_language_and_workflow_guard() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return

    if getattr(st, '_aba_language_and_workflow_guard_v1', False):
        return
    st._aba_language_and_workflow_guard_v1 = True

    try:
        import sitecustomize as sc

        sc.NAV_TOOLS = PREDICTOR_FIRST_NAV_TOOLS
        sc.NAV_NOTES_EN = NAV_NOTES_EN
        sc.NAV_NOTES_ES = NAV_NOTES_ES
    except Exception:
        pass

    try:
        if not st.session_state.get('_aba_language_guard_initialized_v1'):
            st.session_state['global_language'] = 'English'
            _sync_language_keys(st, 'English', include_global=False)
            st.session_state['_aba_language_guard_initialized_v1'] = True
    except Exception:
        pass

    real_st_selectbox = st.selectbox
    real_dg_selectbox = DeltaGenerator.selectbox

    def preferred_index(options: Any) -> int:
        opts = list(options)
        preferred = _normal_language(st.session_state.get('global_language', 'English'))
        return opts.index(preferred) if preferred in opts else 0

    def force_language_kwargs(options: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
        out = dict(kwargs)
        out['key'] = 'global_language'
        out['index'] = preferred_index(options)
        return out

    def remember(value: Any) -> str:
        normalized = _normal_language(value)
        _sync_language_keys(st, normalized, include_global=False)
        return normalized

    def patched_st_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language_selector(label, options):
            kwargs = force_language_kwargs(options, kwargs)
            value = real_st_selectbox(label, options, *args, **kwargs)
            remember(value)
            return value
        return real_st_selectbox(label, options, *args, **kwargs)

    def patched_dg_selectbox(self: Any, label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_language_selector(label, options):
            kwargs = force_language_kwargs(options, kwargs)
            value = real_dg_selectbox(self, label, options, *args, **kwargs)
            remember(value)
            return value
        return real_dg_selectbox(self, label, options, *args, **kwargs)

    st.selectbox = patched_st_selectbox
    DeltaGenerator.selectbox = patched_dg_selectbox


_install_language_and_workflow_guard()
