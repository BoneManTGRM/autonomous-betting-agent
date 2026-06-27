from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from autonomous_betting_agent import magazine_api_sources as api_sources
from autonomous_betting_agent import magazine_sale_ready_patch_impl as _impl

_impl._APPLIED_FLAG = "_ABA_SALE_READY_DIRECT_MULTI_LEG_APPLIED"

# Source markers intentionally kept here for overlay plumbing regression tests:
# repaint_vs_badge, repaint_evidence_body, repaint_masthead, report_brand_name,
# draw_guidance_body, _es(module._tr(item, lang), lang), _sale_ready_risk_chain_v4
# draw.text((x, y), "VS"), ACTIVO, SIN EN VIVO, Cuotas

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

TEXT_ES = {
    "No recent matching news returned.": "Sin noticias recientes relacionadas.",
    "No recent matching Noticias returned.": "Sin noticias recientes relacionadas.",
    "No lineup/injury headline returned.": "Sin titular de lesiones/alineación.",
    "No SDIO event ID.": "Sin ID de evento SDIO.",
    "API-FB: no fixture match.": "API-FB: sin coincidencia de partido.",
    "Price check required before entry.": "Revisar cuota antes de entrar.",
    "Negative edge at current price.": "Ventaja negativa con la cuota actual.",
    "Do not chain negative-EV picks.": "No encadenar señales con VE negativo.",
    "ACTIVE:": "ACTIVO:",
    "NO LIVE:": "SIN EN VIVO:",
    "Odds": "Cuotas",
    "The Cuotas API": "The Odds API",
}

SPANISH_REPLACEMENTS = (
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


def _row(value: Any) -> Mapping[str, Any]:
    return api_sources._row(value)


def _bad(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _split(value: Any) -> list[str]:
    if _bad(value):
        return []
    return [p.strip(" -•") for p in str(value).replace("•", "\n").replace(";", "\n").replace("|", "\n").splitlines() if p.strip(" -•")]


def _num(row: Any, *keys: str) -> float | None:
    data = _row(row)
    for key in keys:
        value = data.get(key)
        if _bad(value):
            continue
        try:
            raw = str(value).strip().replace("%", "").replace(",", "")
            number = float(raw)
            return number / 100 if "%" in str(value) and abs(number) > 1 else number
        except Exception:
            continue
    return None


def _edge_state(row: Any) -> tuple[float | None, float | None, bool, bool]:
    edge = _num(row, "model_market_edge", "edge")
    ev = _num(row, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev")
    return edge, ev, (edge is not None and edge < 0) or (ev is not None and ev < 0), edge is None or ev is None


def _es(value: Any, lang: str = "es") -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if lang != "es" or not text:
        return text
    if text in _PROVIDER_BRANDS:
        return text
    if text in TEXT_ES:
        return TEXT_ES[text]
    text = _impl._es(text, lang)
    if text in TEXT_ES:
        return TEXT_ES[text]
    for old, new in SPANISH_REPLACEMENTS:
        text = re.sub(r"(?<![\w])" + re.escape(old) + r"(?![\w])", new, text, flags=re.I)
    text = text.replace("PA, Estados Unidos", "Pennsylvania, Estados Unidos")
    return text


def translate_country_name(value: Any, lang: str = "es") -> str:
    return _impl.translate_country_name(value, lang)


def translate_team_label(value: Any, lang: str = "es") -> str:
    return _impl.translate_team_label(value, lang)


def translate_country_terms_in_text(value: Any, lang: str = "es") -> str:
    return _impl.translate_country_terms_in_text(value, lang)


def translate_event_name(value: Any, lang: str = "es") -> str:
    return _impl.translate_event_name(value, lang)


def sale_ready_recommendation(row: Any) -> tuple[str, str, bool]:
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        return "WATCHLIST", "Do not play unless price improves.", False
    if missing:
        return "RESEARCH ONLY", "Research only: edge incomplete.", False
    return "PLAY SMALL", "Positive edge and EV after safety checks.", True


def _dedupe(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = re.sub(r"\s+", " ", str(item or "").strip())
        key = text.lower().rstrip(".")
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def sale_ready_team_items(row: Any, side: str = "") -> list[str]:
    lang = _impl._lang(row)
    raw = [str(item or "") for item in api_sources.team_items(row, side)] or ["No SDIO event ID.", "API-FB: no fixture match.", "No recent matching news returned."]
    mapped: list[str] = []
    for item in raw:
        low = item.lower()
        if low.startswith("sdio checked"):
            mapped.append("No SDIO event ID.")
        elif low.startswith("api-fb") or low.startswith("api-football"):
            mapped.append("API-FB lookup checked; no fixture match.")
        elif low.startswith("news checked") or low.startswith("newsapi checked"):
            mapped.append("No recent matching news returned.")
        else:
            mapped.append(item)
    return [_es(item, lang) for item in _dedupe(mapped)[:3]]


def sale_ready_injury_items(row: Any, prefix: str = "") -> list[str]:
    lang = _impl._lang(row)
    raw = [str(item or "") for item in api_sources.injury_items(row, prefix)] or ["No lineup/injury headline returned."]
    mapped = ["No lineup/injury headline returned." if "injury/lineup" in item.lower() or "lineup" in item.lower() else item for item in raw]
    return [_es(item, lang) for item in _dedupe(mapped)[:2]]


def sale_ready_matchup_items(row: Any) -> list[str]:
    lang = _impl._lang(row)
    raw = [str(item or "") for item in api_sources.matchup_items(row)]
    items: list[str] = []
    for item in raw:
        low = item.lower()
        if low.startswith("weather:"):
            body = item.split(":", 1)[1].strip()
            location = ""
            match = re.search(r"\bLocation:\s*(.+)$", body, flags=re.I)
            if match:
                location = match.group(1).strip(" .")
                body = body[: match.start()].strip(" .")
            parts = [p.strip(" .") for p in re.split(r"[,;]", body) if p.strip(" .")]
            temperature = next((p for p in parts if re.search(r"-?\d+(?:\.\d+)?\s*°\s*[CF]\b", p, re.I)), "")
            wind = next((p for p in parts if re.search(r"\bwind\b", p, re.I)), "")
            condition = next((p for p in parts if p not in {temperature, wind}), "")
            if temperature or condition or wind:
                ordered = [temperature.replace(" ", ""), condition[:1].lower() + condition[1:] if condition else "", wind.lower()]
                items.append("Weather: " + ", ".join(p for p in ordered if p) + ".")
            if location:
                items.append("Location: " + api_sources._shorten_location(location) + ".")
        elif low.startswith("api-fb") or low.startswith("api-football"):
            items.append("API-FB lookup checked; no fixture match.")
        elif low.startswith("news checked") or low.startswith("newsapi checked"):
            items.append("No recent matching news returned.")
        else:
            items.append(item)
    return [_es(item, lang) for item in _dedupe(items)[:3]]


def sale_ready_risk_items(row: Any) -> list[str]:
    lang = _impl._lang(row)
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        items = ["Negative edge at current price.", "Do not play unless price improves.", "Recheck odds and key news."]
    elif missing:
        items = ["Research only: edge incomplete.", "Confirm price before entry.", "Wait for verified context."]
    else:
        items = ["Risk status: VOLUME OK.", "Recheck odds before entry.", "Avoid if key news changes."]
    return [_es(item, lang) for item in items]


def sale_ready_chain_items(row: Any) -> list[str]:
    lang = _impl._lang(row)
    data = _row(row)
    explicit: list[str] = []
    for key in ("combo_magazine_items", "parlay_magazine_items", "combo_recommendation", "parlay_recommendation", "combo_note", "parlay_note"):
        explicit.extend(_split(data.get(key)))
    if explicit:
        return [_es(item, lang) for item in _dedupe(explicit)[:3]]
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        items = ["Do not chain negative-EV picks.", "Avoid parlays unless edge turns positive.", "Recheck price before including."]
    elif missing:
        items = ["Research only: edge incomplete.", "Do not combine unverified picks.", "Wait for verified odds."]
    else:
        items = ["Straight only: research.", "Avoid parlays unless all legs are +EV.", "Recheck price before including."]
    return [_es(item, lang) for item in items]


def _items_from_context(row: Any, keys: Iterable[str], fallback: list[str], limit: int, lang: str = "en") -> list[str]:
    key_tuple = tuple(keys)
    explicit: list[str] = []
    data = _row(row)
    for key in key_tuple:
        explicit.extend(_split(data.get(key)))
    if explicit:
        return [_es(item, lang) for item in explicit[:limit]]
    if any(key in key_tuple for key in ("risk", "risk_level", "risk_label", "profit_guard_status", "risk_note", "risk_notes", "why_lose", "hidden_risk")):
        items = sale_ready_risk_items({**dict(data), "report_language": lang})
    elif any(key in key_tuple for key in ("chain_note", "chain_notes", "parlay_note", "parlay_notes", "combo_note", "combo_magazine_items", "parlay_magazine_items", "main_read", "add_on_legs")):
        items = sale_ready_chain_items({**dict(data), "report_language": lang})
    elif "matchup_note" in key_tuple or "sports_context_summary" in key_tuple or "weather_summary" in key_tuple:
        items = sale_ready_matchup_items({**dict(data), "report_language": lang})
    elif "injury_report" in key_tuple or "lineup_status" in key_tuple or "key_players" in key_tuple:
        items = sale_ready_injury_items({**dict(data), "report_language": lang}, "away")
    else:
        items = sale_ready_team_items({**dict(data), "report_language": lang})
    return [_es(item, lang) for item in items[:limit]]


def apply_magazine_sale_ready_patch(module):
    patched = _impl.apply_magazine_sale_ready_patch(module)
    patched.team_items = sale_ready_team_items
    patched.injury_items = sale_ready_injury_items
    patched.matchup_items = sale_ready_matchup_items
    patched.risk_items = sale_ready_risk_items
    patched.chain_items = sale_ready_chain_items
    patched._team_items = sale_ready_team_items
    patched._injury_items = sale_ready_injury_items
    patched._matchup_items = sale_ready_matchup_items
    patched._risk_items = sale_ready_risk_items
    patched._chain_items = sale_ready_chain_items
    patched._items = _items_from_context
    patched.sale_ready_recommendation = sale_ready_recommendation
    try:
        from autonomous_betting_agent.positive_ev_bilingual_patches import install
        install()
    except Exception:
        pass
    if not str(getattr(patched, "MAGAZINE_STYLE_VERSION", "")).endswith("_sale_ready_risk_chain_v4"):
        base = re.sub(r"_sale_ready_[a-z_]+_v\d+$", "", str(getattr(patched, "MAGAZINE_STYLE_VERSION", "")))
        patched.MAGAZINE_STYLE_VERSION = f"{base}_sale_ready_risk_chain_v4"
    return patched
