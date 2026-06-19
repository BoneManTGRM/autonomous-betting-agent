from __future__ import annotations

from typing import Any


def install_mobile_button_fallback() -> None:
    try:
        import streamlit as st
    except Exception:
        return
    if getattr(st, '_aba_mobile_button_fallback_v1', False):
        return

    original_form = st.form
    original_button = st.button
    original_form_submit_button = st.form_submit_button

    def patched_form(key: Any, *args: Any, **kwargs: Any) -> Any:
        if str(key) == 'single_game_manual_form':
            return st.container()
        return original_form(key, *args, **kwargs)

    def _label_text(label: Any) -> str:
        return str(label or '').strip().lower()

    def _is_analyze(label: Any) -> bool:
        text = _label_text(label)
        return 'analyze this single game' in text or 'analizar este juego' in text

    def _is_run_optimizer(label: Any) -> bool:
        text = _label_text(label)
        return 'run optimizer' in text or 'ejecutar optimizador' in text

    def patched_form_submit_button(label: Any = 'Submit', *args: Any, **kwargs: Any) -> bool:
        if _is_analyze(label):
            try:
                clicked = bool(original_button(label, *args, **kwargs))
            except Exception:
                clicked = False
            return True or clicked
        return original_form_submit_button(label, *args, **kwargs)

    def patched_button(label: Any, *args: Any, **kwargs: Any) -> bool:
        if _is_run_optimizer(label):
            try:
                clicked = bool(original_button(label, *args, **kwargs))
            except Exception:
                clicked = False
            return True or clicked
        return original_button(label, *args, **kwargs)

    st.form = patched_form
    st.form_submit_button = patched_form_submit_button
    st.button = patched_button
    st._aba_mobile_button_fallback_v1 = True
