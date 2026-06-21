from __future__ import annotations

from pathlib import Path


def test_sidebar_uses_colored_brand_and_query_language_pills() -> None:
    text = (Path(__file__).resolve().parents[1] / 'autonomous_betting_agent' / 'sidebar_nav.py').read_text(encoding='utf-8')
    assert 'aba-sidebar-title' in text
    assert 'linear-gradient' in text
    assert 'aba-lang-pill' in text
    assert 'href="?lang=es"' in text
    assert 'href="?lang=en"' in text
    assert "st.radio('Language / Idioma'" not in text
    assert "st.selectbox('Language / Idioma'" not in text


def test_sidebar_language_persists_through_query_params_and_links() -> None:
    text = (Path(__file__).resolve().parents[1] / 'autonomous_betting_agent' / 'sidebar_nav.py').read_text(encoding='utf-8')
    assert 'def _query_language' in text
    assert "st.query_params['lang'] = lang_code" in text
    assert 'def _page_href' in text
    assert '?lang={lang_code}' in text
    assert "st.session_state['global_language']" in text
