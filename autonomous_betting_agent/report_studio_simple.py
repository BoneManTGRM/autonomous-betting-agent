from __future__ import annotations

import streamlit as st


def render() -> None:
    st.set_page_config(page_title="Report Studio", layout="wide")
    st.title("Report Studio")
    st.warning("Report Studio is temporarily simplified while the full renderer is restored. The main prediction pages and export modules remain available.")
