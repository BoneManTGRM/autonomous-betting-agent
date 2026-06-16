from __future__ import annotations

from typing import Any

TOOLS: tuple[tuple[str, str, str], ...] = (
    ('Scanner Pro', 'Scanner Pro', 'pages/scanner_pro.py'),
    ('Pro Predictor', 'Predictor Pro', 'pages/pro_predictor.py'),
    ('Ultra 80 Profit Mode', 'Modo Ultra 80 Rentable', 'pages/ultra80_profit_mode.py'),
    ('Simulation Lab', 'Laboratorio de Simulación', 'pages/simulation_lab.py'),
    ('Threshold Optimizer', 'Optimizador de Umbrales', 'pages/threshold_optimizer.py'),
    ('What Are the Odds', 'Cuotas y Valor', 'pages/what_are_the_odds.py'),
    ('Odds Lock Pro', 'Bloqueo de Cuotas Pro', 'pages/odds_lock_pro.py'),
    ('Public Proof Dashboard', 'Dashboard Público de Prueba', 'pages/public_proof_dashboard.py'),
    ('Reset Lock File', 'Reiniciar Archivo de Bloqueo', 'pages/reset_lock_file.py'),
    ('Learning Memory', 'Memoria de Aprendizaje', 'pages/learn_memory.py'),
)

NOTES = {
    'en': (
        'Workflow: Scanner Pro → Pro Predictor → Ultra 80 Profit Mode → Simulation Lab → Odds Lock Pro → Public Proof Dashboard → Threshold Optimizer → Learning Memory.',
        'Use Reset Lock File to clear one test-window proof ledger without touching other test windows.',
    ),
    'es': (
        'Flujo: Scanner Pro → Predictor Pro → Modo Ultra 80 Rentable → Laboratorio de Simulación → Bloqueo de Cuotas Pro → Dashboard Público de Prueba → Optimizador de Umbrales → Memoria de Aprendizaje.',
        'Usa Reiniciar Archivo de Bloqueo para borrar el ledger de una ventana de prueba sin tocar las demás.',
    ),
}


def normalize_language(value: Any) -> str:
    text = str(value or '').strip().lower()
    if text.startswith('es') or 'español' in text or 'espanol' in text:
        return 'es'
    return 'en'


def render_sidebar_nav(language: Any = 'en', *, show_workflow: bool = True) -> None:
    """Render stable navigation links directly on every page.

    This does not rely on Streamlit's native multipage sidebar or a startup hook,
    so it works on Streamlit Cloud/mobile even when sitecustomize is not loaded.
    """
    try:
        import streamlit as st
    except Exception:
        return
    lang = normalize_language(language)
    st.sidebar.markdown('---')
    st.sidebar.markdown('### Herramientas' if lang == 'es' else '### Tools')
    for english, spanish, path in TOOLS:
        label = spanish if lang == 'es' else english
        try:
            st.sidebar.page_link(path, label=label)
        except Exception:
            st.sidebar.caption(label)
    if show_workflow:
        st.sidebar.markdown('---')
        st.sidebar.markdown('### Flujo' if lang == 'es' else '### Workflow')
        for note in NOTES[lang]:
            st.sidebar.caption(note)
