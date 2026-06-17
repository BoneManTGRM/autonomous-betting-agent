from __future__ import annotations

import streamlit as st

APP_NAME = "ARA Signal Pro"
APP_TAGLINE = "Powered by Reparodynamics"

st.set_page_config(
    page_title=APP_NAME,
    layout="wide",
    initial_sidebar_state="expanded",
)

# Use the shared language selector state from the pages. The navigation is built
# before each page renders, so it must read session state directly to translate
# sidebar page labels on rerun.
LANG_VALUE = st.session_state.get("pro_predictor_language", "English")
LANG = "es" if LANG_VALUE == "Español" else "en"

NAV_LABELS = {
    "en": {
        "pro_predictor": "Pro Predictor",
        "ultra70_profit_mode": "Ultra 70 Profit Mode",
        "simulation_lab": "Simulation Lab",
        "threshold_optimizer": "Threshold Optimizer",
        "what_are_the_odds": "What Are the Odds",
        "odds_lock_pro": "Odds Lock Pro",
        "public_proof_dashboard": "Public Proof Dashboard",
        "learning_memory": "Learning Memory",
        "reset_lock_file": "Reset Lock File",
        "workflow": "Workflow",
        "workflow_path": "Pro Predictor → Highest Confidence → Odds Lock Pro → Public Proof Dashboard → Learning Memory.",
        "workflow_note": "Odds Lock Pro timestamps locked picks; Public Proof Dashboard shows ROI and results.",
    },
    "es": {
        "pro_predictor": "Predictor Pro",
        "ultra70_profit_mode": "Modo de Ganancia Ultra 70",
        "simulation_lab": "Laboratorio de Simulación",
        "threshold_optimizer": "Optimizador de Umbral",
        "what_are_the_odds": "Qué Probabilidades Hay",
        "odds_lock_pro": "Odds Lock Pro",
        "public_proof_dashboard": "Dashboard Público de Prueba",
        "learning_memory": "Memoria de Aprendizaje",
        "reset_lock_file": "Reiniciar Archivo de Bloqueo",
        "workflow": "Flujo de trabajo",
        "workflow_path": "Predictor Pro → Máxima Confianza → Odds Lock Pro → Dashboard Público → Memoria de Aprendizaje.",
        "workflow_note": "Odds Lock Pro marca picks bloqueados con hora; el Dashboard Público muestra ROI y resultados.",
    },
}


def nav_text(key: str) -> str:
    return NAV_LABELS[LANG].get(key, NAV_LABELS["en"].get(key, key))


# Brand stays in the sidebar without replacing navigation.
st.sidebar.markdown("### :green[ARA] Signal :red[Pro]")
st.sidebar.caption(APP_TAGLINE)
st.sidebar.markdown("---")

PAGES = [
    st.Page("pages/pro_predictor.py", title=nav_text("pro_predictor")),
    st.Page("pages/ultra80_profit_mode.py", title=nav_text("ultra70_profit_mode")),
    st.Page("pages/simulation_lab.py", title=nav_text("simulation_lab")),
    st.Page("pages/threshold_optimizer.py", title=nav_text("threshold_optimizer")),
    st.Page("pages/what_are_the_odds.py", title=nav_text("what_are_the_odds")),
    st.Page("pages/odds_lock_pro.py", title=nav_text("odds_lock_pro")),
    st.Page("pages/public_proof_dashboard.py", title=nav_text("public_proof_dashboard")),
    st.Page("pages/learn_memory.py", title=nav_text("learning_memory")),
    st.Page("pages/reset_lock_file.py", title=nav_text("reset_lock_file")),
]

# Curated navigation must stay visible in the sidebar. Do not disable
# [client].showSidebarNavigation in .streamlit/config.toml.
current_page = st.navigation(PAGES, position="sidebar", expanded=True)


def _ignore_late_page_config(*args, **kwargs):
    return None


# Existing page files still call set_page_config; ignore those after the main app config.
st.set_page_config = _ignore_late_page_config
current_page.run()

# Explainer stays at the bottom of the sidebar after page controls render.
st.sidebar.markdown("---")
st.sidebar.markdown(f"### {nav_text('workflow')}")
st.sidebar.caption(nav_text("workflow_path"))
st.sidebar.caption(nav_text("workflow_note"))
