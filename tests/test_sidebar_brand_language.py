from __future__ import annotations

from pathlib import Path


def test_sidebar_uses_colored_brand_and_radio_language_selector() -> None:
    text = (Path(__file__).resolve().parents[1] / 'autonomous_betting_agent' / 'sidebar_nav.py').read_text(encoding='utf-8')
    assert 'aba-sidebar-title' in text
    assert 'linear-gradient' in text
    assert "selector: str = 'radio'" in text
    assert "st.radio('Language / Idioma'" in text
    assert "st.selectbox('Language / Idioma'" not in text
