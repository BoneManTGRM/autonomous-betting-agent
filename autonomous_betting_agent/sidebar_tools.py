from __future__ import annotations

from typing import Any

import pandas as pd


def normal_language(value: object) -> str:
    text = str(value or '').lower()
    return 'Español' if text.startswith('es') or 'español' in text or 'espanol' in text else 'English'


def sync_language(st: Any, value: object) -> str:
    lang = normal_language(value)
    for key in ('global_language', 'app_language'):
        try:
            st.session_state[key] = lang
        except Exception:
            pass
    return lang


def is_language_widget(label: Any, options: Any) -> bool:
    try:
        opts = list(options)
    except Exception:
        return False
    text = str(label or '').lower()
    return 'English' in opts and 'Español' in opts and ('language' in text or 'idioma' in text)


def inject_sidebar_css(st: Any) -> None:
    return None


def render_sidebar_brand(st: Any) -> None:
    return None


def render_curated_sidebar(st: Any, language: object = 'English') -> None:
    return None


def sidebar_language_selector(st: Any, *, key: str, default: str = 'English') -> str:
    try:
        value = st.session_state.get(key, st.session_state.get('global_language', default))
    except Exception:
        value = default
    return 'es' if normal_language(value) == 'Español' else 'en'


def install_sidebar_tools() -> None:
    return None


def session_state_summary() -> pd.DataFrame:
    return pd.DataFrame()


def proof_sidebar_snapshot() -> dict[str, int]:
    return {'pro_predictor_rows': 0, 'high_confidence_rows': 0, 'locked_rows': 0}
