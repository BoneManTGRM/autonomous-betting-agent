from __future__ import annotations

import streamlit as st

APP_NAME = "ABA Signal Pro"
APP_TAGLINE = "Powered by Reparodynamics"

st.set_page_config(
    page_title=APP_NAME,
    layout="wide",
    initial_sidebar_state="expanded",
)

with st.sidebar:
    st.markdown("### :green[ABA] Signal :red[Pro]")
    st.caption(APP_TAGLINE)
    st.markdown("---")


def _ignore_late_page_config(*args, **kwargs):
    return None


st.set_page_config = _ignore_late_page_config

import streamlit_app  # noqa: F401,E402
