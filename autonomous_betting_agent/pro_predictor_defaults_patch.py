from __future__ import annotations

from typing import Any

# Target profile based on Cody's larger-list result:
# 108 picks, 60 finished, 43-17 = 71.7% while still maintaining useful volume.
# This does not guarantee 70%+, but it sets Pro Predictor's defaults to reproduce
# the same style: broad enough volume, light filters, then top-ranked export.
NUMBER_DEFAULTS = {
    'Max sports': 50,
    'Máximo de deportes': 50,
    'Max events per sport': 500,
    'Máximo de eventos por deporte': 500,
}

MULTI_DEFAULTS = {
    'Bookmaker regions': ['us', 'us2', 'eu', 'uk'],
    'Regiones de casas': ['us', 'us2', 'eu', 'uk'],
    'Markets': ['h2h'],
    'Mercados': ['h2h'],
}

PROFILE_VALUES = {
    # Main default profile: Large List 70 Mode.
    'baseline_accuracy_min_books': 1,
    'baseline_accuracy_min_model_prob': 0.58,
    'baseline_accuracy_min_edge': -0.03,
    'baseline_accuracy_strong_edge': 0.04,
    'baseline_accuracy_min_strength': 38.0,
    'baseline_accuracy_use_high_conf': True,
    'baseline_accuracy_max_high_conf': 108,
    'baseline_accuracy_min_high_prob': 0.58,
    'baseline_accuracy_min_high_edge': -0.03,
    'baseline_accuracy_min_high_strength': 38.0,
    'baseline_accuracy_min_high_agent': 35.0,
    # Secondary profile: smaller but still usable volume.
    'balanced_confidence_min_books': 1,
    'balanced_confidence_min_model_prob': 0.60,
    'balanced_confidence_min_edge': -0.02,
    'balanced_confidence_strong_edge': 0.03,
    'balanced_confidence_min_strength': 45.0,
    'balanced_confidence_use_high_conf': True,
    'balanced_confidence_max_high_conf': 75,
    'balanced_confidence_min_high_prob': 0.60,
    'balanced_confidence_min_high_edge': -0.015,
    'balanced_confidence_min_high_strength': 45.0,
    'balanced_confidence_min_high_agent': 45.0,
    # Elite profile: much smaller lock/watchlist.
    'profit_strict_min_books': 2,
    'profit_strict_min_model_prob': 0.62,
    'profit_strict_min_edge': 0.01,
    'profit_strict_strong_edge': 0.05,
    'profit_strict_min_strength': 55.0,
    'profit_strict_use_high_conf': True,
    'profit_strict_max_high_conf': 25,
    'profit_strict_min_high_prob': 0.64,
    'profit_strict_min_high_edge': 0.00,
    'profit_strict_min_high_strength': 55.0,
    'profit_strict_min_high_agent': 55.0,
}

# Old/bad defaults that should be migrated automatically when a browser session
# already cached them before the Large List 70 profile existed.
STALE_VALUES = {
    'baseline_accuracy_max_high_conf': {250, 500},
    'baseline_accuracy_min_high_prob': {0.60, 0.62},
    'baseline_accuracy_min_high_strength': {40.0, 50.0},
    'baseline_accuracy_min_high_agent': {40.0, 50.0},
}


def _is_stale_value(key: str, current: Any) -> bool:
    if current in (None, ''):
        return True
    if key not in STALE_VALUES:
        return False
    try:
        current_number = float(current)
    except Exception:
        return current in STALE_VALUES[key]
    return any(abs(current_number - float(old)) < 1e-9 for old in STALE_VALUES[key])


def apply_large_list_70_defaults(st_module: Any) -> None:
    """Set Pro Predictor widget defaults without monkey-patching Streamlit.

    This fixes stale sessions showing the old 250 / 0.60 / 40 / 40 high-confidence
    settings. It only writes normal Streamlit session-state values before widgets
    render; it does not override buttons, forms, uploaders, or download controls.
    """
    try:
        for key, value in PROFILE_VALUES.items():
            current = st_module.session_state.get(key)
            if key.startswith('baseline_accuracy_'):
                # Force the Large List 70 baseline to the target values every page load.
                st_module.session_state[key] = value
            elif current is None:
                st_module.session_state[key] = value
            elif _is_stale_value(key, current):
                st_module.session_state[key] = value
        st_module.session_state['_large_list_70_defaults_applied_v3'] = True
    except Exception:
        pass


def install_pro_predictor_defaults_patch() -> None:
    try:
        import streamlit as st
    except Exception:
        return
    apply_large_list_70_defaults(st)
