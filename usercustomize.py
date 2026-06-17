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
)

NAV_NOTES_EN = (
    'Workflow: Pro Predictor → Ultra 70 Profit Mode → Simulation Lab → Odds Lock Pro → Public Proof Dashboard → Learning Memory.',
    'Start in Pro Predictor. Scanner Pro is not part of the active workflow.',
    'Use Reset Lock File only when clearing one test-window proof ledger without touching other windows.',
)
NAV_NOTES_ES = (
    'Flujo: Predictor Pro → Ultra 70 Profit Mode → Laboratorio de Simulación → Bloqueo de Cuotas Pro → Dashboard Público → Memoria.',
    'Empieza en Predictor Pro. Scanner Pro no forma parte del flujo activo.',
    'Usa Reiniciar Archivo de Bloqueo solo para borrar un ledger de prueba sin tocar otros.',
)

FLAT_GUIDES: dict[str, dict[str, dict[str, str]]] = {
    'pro_predictor': {
        'en': {'name': 'Pro Predictor', 'purpose': 'Primary live prediction search and scoring page.', 'next': 'Ultra 70 Profit Mode → Simulation Lab → Odds Lock Pro'},
        'es': {'name': 'Predictor Pro', 'purpose': 'Página principal para búsqueda y calificación en vivo.', 'next': 'Ultra 70 Profit Mode → Simulation Lab → Odds Lock Pro'},
    },
    'ultra80_profit_mode': {
        'en': {'name': 'Ultra 70 Profit Mode', 'purpose': 'Review and tier the strongest Pro Predictor rows.', 'next': 'Simulation Lab → Odds Lock Pro'},
        'es': {'name': 'Ultra 70 Profit Mode', 'purpose': 'Revisa y clasifica las filas más fuertes de Predictor Pro.', 'next': 'Simulation Lab → Odds Lock Pro'},
    },
    'simulation_lab': {
        'en': {'name': 'Simulation Lab', 'purpose': 'Stress-test selected rows before final use.', 'next': 'Odds Lock Pro'},
        'es': {'name': 'Simulation Lab', 'purpose': 'Prueba de estrés para filas seleccionadas antes del uso final.', 'next': 'Odds Lock Pro'},
    },
    'what_are_the_odds': {
        'en': {'name': 'What Are the Odds', 'purpose': 'Review odds quality, value, manual context, and decision scoring.', 'next': 'Odds Lock Pro'},
        'es': {'name': 'What Are the Odds', 'purpose': 'Revisa calidad de cuotas, valor, contexto manual y decisión.', 'next': 'Odds Lock Pro'},
    },
    'odds_lock_pro': {
        'en': {'name': 'Odds Lock Pro', 'purpose': 'Create timestamped final rows before events start.', 'next': 'Public Proof Dashboard'},
        'es': {'name': 'Odds Lock Pro', 'purpose': 'Crea filas finales con timestamp antes de que empiecen eventos.', 'next': 'Dashboard Público'},
    },
    'public_proof_dashboard': {
        'en': {'name': 'Public Proof Dashboard', 'purpose': 'Review locked rows, metrics, results, and reports.', 'next': 'Learning Memory'},
        'es': {'name': 'Dashboard Público', 'purpose': 'Revisa filas bloqueadas, métricas, resultados y reportes.', 'next': 'Learning Memory'},
    },
    'learning_memory': {
        'en': {'name': 'Learning Memory', 'purpose': 'Update calibration and long-term memory after grading.', 'next': 'Future Pro Predictor runs'},
        'es': {'name': 'Learning Memory', 'purpose': 'Actualiza calibración y memoria después de calificar.', 'next': 'Futuras corridas de Predictor Pro'},
    },
    'threshold_optimizer': {
        'en': {'name': 'Threshold Optimizer', 'purpose': 'Learn better cutoffs after enough graded results.', 'next': 'Future Pro Predictor runs'},
        'es': {'name': 'Threshold Optimizer', 'purpose': 'Aprende mejores cortes después de suficientes resultados.', 'next': 'Futuras corridas de Predictor Pro'},
    },
    'reset_lock_file': {
        'en': {'name': 'Reset Lock File', 'purpose': 'Reset one test-window ledger intentionally.', 'next': 'Odds Lock Pro'},
        'es': {'name': 'Reset Lock File', 'purpose': 'Reinicia una ventana de prueba intencionalmente.', 'next': 'Odds Lock Pro'},
    },
}


def _normal_language(value: object) -> str:
    text = str(value or '').strip().lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'Español'
    return 'English'


def _lang_key(value: object) -> str:
    return 'es' if _normal_language(value) == 'Español' else 'en'


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


def _install_flat_sidebar_override() -> None:
    try:
        import streamlit as st
        import autonomous_betting_agent.tool_sidebar as sidebar
    except Exception:
        return

    sidebar.WORKFLOW = [item[0] for item in PREDICTOR_FIRST_NAV_TOOLS]

    def flat_render_tool_sidebar(page_key: str, language: str = 'English') -> None:
        lang = _lang_key(language)
        guide = FLAT_GUIDES.get(page_key, FLAT_GUIDES['pro_predictor']).get(lang, FLAT_GUIDES['pro_predictor']['en'])
        labels = {
            'en': {'guide': 'Tool guide', 'purpose': 'Purpose', 'next': 'Next', 'workflow': 'Workflow'},
            'es': {'guide': 'Guía de herramienta', 'purpose': 'Propósito', 'next': 'Siguiente', 'workflow': 'Flujo'},
        }[lang]
        st.sidebar.markdown('### :green[ABA] Signal :red[Pro]')
        st.sidebar.caption('Powered by Reparodynamics')
        st.sidebar.divider()
        st.sidebar.subheader(labels['guide'])
        st.sidebar.markdown(f"**{guide['name']}**")
        st.sidebar.caption(f"{labels['purpose']}: {guide['purpose']}")
        st.sidebar.caption(f"{labels['next']}: {guide['next']}")
        st.sidebar.caption(f"{labels['workflow']}: {' → '.join(sidebar.WORKFLOW[:6])}")

    sidebar.render_tool_sidebar = flat_render_tool_sidebar


def _install_language_and_workflow_guard() -> None:
    try:
        import streamlit as st
        from streamlit.delta_generator import DeltaGenerator
    except Exception:
        return

    if getattr(st, '_aba_language_and_workflow_guard_v2', False):
        return
    st._aba_language_and_workflow_guard_v2 = True

    try:
        import sitecustomize as sc

        sc.NAV_TOOLS = PREDICTOR_FIRST_NAV_TOOLS
        sc.NAV_NOTES_EN = NAV_NOTES_EN
        sc.NAV_NOTES_ES = NAV_NOTES_ES
    except Exception:
        pass

    _install_flat_sidebar_override()

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
