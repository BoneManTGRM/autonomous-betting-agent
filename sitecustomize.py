from __future__ import annotations

import builtins
import os


def get_secret(*names: str) -> str:
    try:
        import streamlit as st
    except Exception:
        st = None  # type: ignore[assignment]
    for name in names:
        if not name:
            continue
        if st is not None:
            try:
                value = str(st.secrets.get(name, '')).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


builtins.get_secret = get_secret


def _install_all_runtime_hooks() -> None:
    try:
        import streamlit as st
        from autonomous_betting_agent.sidebar_tools import install_sidebar_tools, render_curated_sidebar, normal_language
        install_sidebar_tools()
        try:
            language = normal_language(st.session_state.get('global_language', 'English'))
            if not st.session_state.get('_ara_startup_sidebar_drawn'):
                st.session_state['_ara_startup_sidebar_drawn'] = True
                render_curated_sidebar(st, language)
        except Exception:
            pass
    except Exception:
        pass
    try:
        from autonomous_betting_agent.odds_input_normalizer import install_odds_breakdown_normalizer
        install_odds_breakdown_normalizer()
    except Exception:
        pass
    try:
        from autonomous_betting_agent.proof_dashboard_patch import install_proof_dashboard_patch
        install_proof_dashboard_patch()
    except Exception:
        pass
    try:
        from autonomous_betting_agent.local_users import install_streamlit_local_user_selector
        install_streamlit_local_user_selector()
    except Exception:
        pass


_install_all_runtime_hooks()
