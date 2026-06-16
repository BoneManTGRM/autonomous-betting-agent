"""Legacy Streamlit entrypoint for ABA Signal Pro.

This file is used by deployments that still point to app_streamlit.py.
It must set the visible sidebar branding before importing streamlit_app.py.
"""

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
    st.markdown("## ABA Signal Pro")
    st.success("ABA")
    st.markdown("### Signal")
    st.error("Pro")
    st.caption(APP_TAGLINE)
    st.markdown("---")

st.session_state["aba_sidebar_brand_rendered"] = True


def _ignore_late_page_config(*args, **kwargs):
    return None


st.set_page_config = _ignore_late_page_config

import streamlit_app  # noqa: F401,E402
