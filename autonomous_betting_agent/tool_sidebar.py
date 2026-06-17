from __future__ import annotations

import pandas as pd
import streamlit as st

APP_TAGLINE = 'Powered by Reparodynamics'
PREDICTOR_TOOL_NAME = 'Pro Predictor'

WORKFLOW = [
    PREDICTOR_TOOL_NAME,
    'Ultra 70 Profit Mode',
    'Simulation Lab',
    'Odds Lock Pro',
    'Public Proof Dashboard',
    'Learning Memory',
]

PAGE_GUIDES = {
    'pro_predictor': {
        'en': ('Pro Predictor', 'Primary prediction search and scoring page.', 'Ultra 70 Profit Mode → Simulation Lab → Odds Lock Pro'),
        'es': ('Predictor Pro', 'Página principal de búsqueda y calificación.', 'Ultra 70 Profit Mode → Simulation Lab → Odds Lock Pro'),
    },
    'ultra80_profit_mode': {
        'en': ('Ultra 70 Profit Mode', 'Reviews and tiers the strongest Pro Predictor rows.', 'Simulation Lab → Odds Lock Pro'),
        'es': ('Ultra 70 Profit Mode', 'Revisa y clasifica las filas más fuertes de Predictor Pro.', 'Simulation Lab → Odds Lock Pro'),
    },
    'simulation_lab': {
        'en': ('Simulation Lab', 'Stress-tests selected rows before final use.', 'Odds Lock Pro'),
        'es': ('Simulation Lab', 'Prueba de estrés para filas seleccionadas.', 'Odds Lock Pro'),
    },
    'what_are_the_odds': {
        'en': ('What Are the Odds', 'Reviews value, odds quality, manual context, and decision scoring.', 'Odds Lock Pro'),
        'es': ('What Are the Odds', 'Revisa valor, calidad de cuotas, contexto manual y decisión.', 'Odds Lock Pro'),
    },
    'odds_lock_pro': {
        'en': ('Odds Lock Pro', 'Creates timestamped final rows before events start.', 'Public Proof Dashboard'),
        'es': ('Odds Lock Pro', 'Crea filas finales con timestamp antes de eventos.', 'Dashboard Público'),
    },
    'public_proof_dashboard': {
        'en': ('Public Proof Dashboard', 'Reviews saved rows, metrics, results, and reports.', 'Learning Memory'),
        'es': ('Dashboard Público', 'Revisa filas guardadas, métricas, resultados y reportes.', 'Learning Memory'),
    },
    'learning_memory': {
        'en': ('Learning Memory', 'Updates calibration and long-term memory after grading.', 'Future Pro Predictor runs'),
        'es': ('Learning Memory', 'Actualiza calibración y memoria después de calificar.', 'Futuras corridas de Predictor Pro'),
    },
    'threshold_optimizer': {
        'en': ('Threshold Optimizer', 'Learns better cutoff settings after enough graded rows.', 'Future Pro Predictor runs'),
        'es': ('Threshold Optimizer', 'Aprende mejores cortes después de suficientes filas.', 'Futuras corridas de Predictor Pro'),
    },
    'reset_lock_file': {
        'en': ('Reset Lock File', 'Resets one test-window ledger intentionally.', 'Odds Lock Pro'),
        'es': ('Reset Lock File', 'Reinicia una ventana de prueba.', 'Odds Lock Pro'),
    },
}


def _lang_key(language: str) -> str:
    return 'es' if str(language).lower().startswith('es') else 'en'


def _count_session_rows(key: str) -> int:
    rows = st.session_state.get(key) or []
    try:
        return int(len(rows))
    except TypeError:
        return 0


def session_state_summary() -> pd.DataFrame:
    return pd.DataFrame([
        {'stage': 'Pro Predictor handoff', 'session_key': 'pro_predictor_latest_rows', 'rows': _count_session_rows('pro_predictor_latest_rows')},
        {'stage': 'High-confidence rows', 'session_key': 'pro_predictor_high_confidence_rows', 'rows': _count_session_rows('pro_predictor_high_confidence_rows')},
        {'stage': 'Ultra 70 rows', 'session_key': 'ultra80_max_volume_rows', 'rows': _count_session_rows('ultra80_max_volume_rows')},
        {'stage': 'Simulation survivors', 'session_key': 'simulation_survivor_rows', 'rows': _count_session_rows('simulation_survivor_rows')},
        {'stage': 'Locked rows', 'session_key': 'odds_lock_pro_locked_rows', 'rows': _count_session_rows('odds_lock_pro_locked_rows')},
    ])


def proof_sidebar_snapshot() -> dict[str, int]:
    return {
        'pro_predictor_rows': _count_session_rows('pro_predictor_latest_rows'),
        'high_confidence_rows': _count_session_rows('pro_predictor_high_confidence_rows'),
        'locked_rows': _count_session_rows('odds_lock_pro_locked_rows'),
    }


def render_tool_sidebar(page_key: str, language: str = 'English') -> None:
    # The single supported sidebar is rendered by autonomous_betting_agent.sidebar_tools.
    return None
