from __future__ import annotations

import re
from typing import Any

from autonomous_betting_agent import magazine_sale_ready_patch_impl as _impl

_impl._APPLIED_FLAG = "_ABA_SALE_READY_DIRECT_MULTI_LEG_APPLIED"

_PROVIDER_BRANDS = {
    "The Odds API",
    "Odds API",
    "SportsDataIO",
    "WeatherAPI",
    "API-Football",
    "NewsAPI",
    "Perplexity",
    "Playdoit",
}

_SPANISH_REPLACEMENTS = (
    ("The Cuotas API", "The Odds API"),
    ("Light rain", "lluvia ligera"),
    ("Rain", "lluvia"),
    ("Weather", "Clima"),
    ("wind", "viento"),
    ("Wind", "Viento"),
    ("Location", "Ubicación"),
    ("Temperature", "Temperatura"),
    ("Humidity", "Humedad"),
    ("Forecast", "Pronóstico"),
    ("News checked", "Noticias revisadas"),
    ("no recent matching articles", "sin artículos recientes relacionados"),
    ("no recent related articles", "sin artículos recientes relacionados"),
    ("no injury/lineup headline", "sin titular de lesiones/alineación"),
    ("Philadelphia", "Filadelfia"),
    ("United States of America", "Estados Unidos"),
    ("United States", "Estados Unidos"),
    ("USA", "Estados Unidos"),
)


def _es(value: Any, lang: str = "es") -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if lang != "es" or not text:
        return text
    if text in _PROVIDER_BRANDS:
        return text
    text = _impl._es(text, lang)
    for old, new in _SPANISH_REPLACEMENTS:
        text = re.sub(r"(?<![\w])" + re.escape(old) + r"(?![\w])", new, text, flags=re.I)
    text = text.replace("PA, Estados Unidos", "Pennsylvania, Estados Unidos")
    return text


def apply_magazine_sale_ready_patch(module):
    patched = _impl.apply_magazine_sale_ready_patch(module)
    try:
        from autonomous_betting_agent.positive_ev_bilingual_patches import install
        install()
    except Exception:
        pass
    return patched


def sale_ready_matchup_items(row):
    lang = _impl._lang(row)
    return [_es(item, lang) for item in _impl.sale_ready_matchup_items(row)]


def sale_ready_team_items(row, side=""):
    lang = _impl._lang(row)
    return [_es(item, lang) for item in _impl.sale_ready_team_items(row, side)]


def sale_ready_injury_items(row, prefix=""):
    lang = _impl._lang(row)
    return [_es(item, lang) for item in _impl.sale_ready_injury_items(row, prefix)]


def sale_ready_chain_items(row):
    lang = _impl._lang(row)
    return [_es(item, lang) for item in _impl.sale_ready_chain_items(row)]


def sale_ready_risk_items(row):
    lang = _impl._lang(row)
    return [_es(item, lang) for item in _impl.sale_ready_risk_items(row)]


sale_ready_recommendation = _impl.sale_ready_recommendation
translate_country_name = _impl.translate_country_name
translate_team_label = _impl.translate_team_label
translate_event_name = _impl.translate_event_name
translate_country_terms_in_text = _impl.translate_country_terms_in_text
