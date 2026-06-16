from __future__ import annotations

import streamlit as st

APP_NAME = "ABA Signal Pro"

st.set_page_config(
    page_title=APP_NAME,
    layout="wide",
    initial_sidebar_state="expanded",
)


def _ignore_late_page_config(*args, **kwargs):
    return None


st.set_page_config = _ignore_late_page_config

import streamlit_app  # noqa: F401,E402
