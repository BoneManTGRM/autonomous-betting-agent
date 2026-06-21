from __future__ import annotations

from pathlib import Path


def test_sidebar_uses_colored_brand_and_radio_language_selector() -> None:
    text = (Path(__file__).resolve().parents[1] / 'autonomous_betting_agent' / 'sidebar_nav.py').read_text(encoding='utf-8')
    assert 'aba-sidebar-title' in text
    assert 'linear-gradient' in text
    assert "selector: str = 'radio'" in text
    assert "st.radio('Language / Idioma'" in text
    assert "st.selectbox('Language / Idioma'" not in text


def test_sidebar_language_uses_single_global_widget_key() -> None:
    text = (Path(__file__).resolve().parents[1] / 'autonomous_betting_agent' / 'sidebar_nav.py').read_text(encoding='utf-8')
    assert "st.radio('Language / Idioma', ['English', 'Español'], key='global_language'" in text
    assert "st.session_state['global_language']" in text
    assert 'st.session_state[language_key] = starting_language' not in text
    assert 'def _sync_language' not in text
