from __future__ import annotations

import streamlit as st

SESSION_KEY = 'app_language'
OPTIONS = ['English', 'Español']
PAGE_LANGUAGE_KEYS = [
    'language_settings_language',
    'tool_command_center_language',
    'command_center_language',
    'game_intelligence_language',
    'deployment_health_language',
    'scanner_pro_language',
    'pro_predictor_language',
    'what_are_the_odds_language',
    'what_are_the_odds_pro_language',
    'odds_lock_pro_language',
    'public_proof_dashboard_language',
    'auto_result_grading_language',
    'daily_workflow_language',
    'learning_memory_language',
    'learn_memory_language',
    'monthly_license_readiness_language',
    'buyer_demo_mode_language',
    'daily_operator_checklist_language',
    'private_beta_sales_dashboard_language',
    'reset_data_language',
]


def _code(value: object) -> str:
    text = str(value or 'English').strip().lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'es'
    return 'en'


def label(value: object = None) -> str:
    return 'Español' if _code(value if value is not None else st.session_state.get(SESSION_KEY, 'English')) == 'es' else 'English'


def query_param_language() -> str | None:
    try:
        raw = st.query_params.get('lang')
    except Exception:
        return None
    if not raw:
        return None
    return label(raw)


def _safe_set_session(key: str, value: str) -> None:
    try:
        st.session_state[key] = value
    except Exception:
        # Streamlit blocks mutating a widget's own key after that widget is instantiated.
        # The widget already contains the selected value, so skipping that key is safe.
        pass


def set_global_language(selected: object) -> str:
    normalized = label(selected)
    _safe_set_session(SESSION_KEY, normalized)
    _safe_set_session('global_language', normalized)
    for key in PAGE_LANGUAGE_KEYS:
        _safe_set_session(key, normalized)
    try:
        st.query_params['lang'] = 'es' if normalized == 'Español' else 'en'
    except Exception:
        pass
    return normalized


def current_language_label(default: object = 'Español') -> str:
    return label(query_param_language() or st.session_state.get('global_language') or st.session_state.get(SESSION_KEY) or default)


def render_language_selector(*, key: str) -> str:
    current = current_language_label()
    _safe_set_session(key, current)

    def _sync_language() -> None:
        set_global_language(st.session_state.get(key) or st.session_state.get('global_language') or current)

    selected = st.sidebar.selectbox('Language / Idioma', OPTIONS, index=OPTIONS.index(current), key=key, on_change=_sync_language)
    set_global_language(selected)
    return _code(selected)
