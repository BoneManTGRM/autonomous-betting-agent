from __future__ import annotations

import streamlit as st

SESSION_KEY = "app_language"
OPTIONS = ["English", "Español"]


def _code(value: object) -> str:
    text = str(value or "English").strip().lower()
    if text.startswith("es") or "español" in text or "espanol" in text:
        return "es"
    return "en"


def label(value: object = None) -> str:
    return "Español" if _code(value if value is not None else st.session_state.get(SESSION_KEY, "English")) == "es" else "English"


def render_language_selector(*, key: str) -> str:
    current = label(st.session_state.get(SESSION_KEY, "English"))
    if key in st.session_state:
        current = label(st.session_state[key])
    selected = st.sidebar.selectbox("Language / Idioma", OPTIONS, index=OPTIONS.index(current), key=key)
    st.session_state[SESSION_KEY] = selected
    return _code(selected)
