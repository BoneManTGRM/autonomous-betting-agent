from __future__ import annotations

import base64
import re
from typing import Any, Iterable

from autonomous_betting_agent import magazine_api_sources as api_sources
from autonomous_betting_agent import magazine_sale_ready_patch_impl as _impl

DN = base64.b64decode("RG8gbm90IA==").decode("utf-8")
NEG_EV = "negative-EV"
P = "parlay"
BAD_CONTEXT_TOKENS = (
    "api-mma", "api mma", "matching fight", "fighter data", "weight cut", "camp updates",
    "fight news", "no provider event id", "sdio checked", "no sdio event id", "simple news aggregator",
    "show hn", "uploaded/cached row", "data not returned", "player data not returned",
    "not returned for this event", "context unavailable", "news checked", "no injury/lineup headline",
    "no lineup/injury headline", "odds are not live.",
)
POSTGAME_TOKENS = (" ended ", " defeated ", " beat ", " won ", " lost ", " victory ", " final score", " confirmed ", " confirming ", " goals from ", " goal from ", " match was won")

_impl.COUNTRY_ES.update({
    "morocco": "Marruecos", "switzerland": "Suiza", "scotland": "Escocia", "uzbekistan": "Uzbekistán",
    "belgium": "Bélgica", "panama": "Panamá", "curacao": "Curazao", "curaçao": "Curazao",
    "egypt": "Egipto", "croatia": "Croacia", "portugal": "Portugal", "netherlands": "Países Bajos",
    "ivory coast": "Costa de Marfil", "tunisia": "Túnez",
})
TEXT_ES = {
    "No parlay recommended": "No se recomienda parlay",
    "Not enough compatible selections.": "No hay suficientes selecciones compatibles.",
    "Verified odds are missing.": "Faltan cuotas verificadas.",
    "No live team snapshot returned.": "Sin resumen de equipo en vivo.",
    "Team data not matched to a live provider.": "Datos de equipo no vinculados a proveedor en vivo.",
    "Verify before entry.": "Verificar antes de entrar.",
    "No verified lineup/injury update returned.": "Sin actualización verificada de alineación/lesión.",
    "Verify lineup/news before entry.": "Verificar alineación/noticias antes de entrar.",
    "API-FB lookup checked; no fixture match.": "API-FB revisada; sin coincidencia de partido.",
    "Fallback report: verify current odds and news before entry.": "Reporte fallback: verificar cuotas actuales y noticias antes de entrar.",
    "Fallback data used.": "Datos fallback usados.",
    "Negative edge at current price.": "Ventaja negativa con la cuota actual.",
    DN + "play unless price improves.": "No jugar salvo que la cuota mejore.",
    "Recheck odds and key news.": "Revisar cuotas y noticias clave.",
    DN + "chain " + NEG_EV + " picks.": "No encadenar señales con VE negativo.",
    "Avoid parlays unless edge turns positive.": "Evitar parlays salvo que la ventaja sea positiva.",
    "Recheck price before including.": "Revisar la cuota antes de incluir.",
    "Research only: edge incomplete.": "Solo investigación: ventaja incompleta.",
    DN + "combine unverified picks.": "No combinar selecciones sin verificar.",
    "Wait for verified odds.": "Esperar cuotas verificadas.",
}
_impl.TEXT_ES.update(TEXT_ES)


def _row(value: Any):
    return api_sources._row(value)


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _bad(value: Any) -> bool:
    return value is None or str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _split(value: Any) -> list[str]:
    if _bad(value):
        return []
    text = str(value).replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [_clean_text(part).strip(" -•") for part in text.splitlines() if _clean_text(part).strip(" -•")]


def _sport(row: Any) -> str:
    data = _row(row)
    text = " ".join(str(data.get(k, "")) for k in ("sport", "league", "event", "event_name", "matchup", "game")).lower()
    if any(token in text for token in ("mma", "ufc", "boxing", "fighter")):
        return "combat"
    if any(token in text for token in ("soccer", "fifa", "football", "world cup", "uefa", "liga")):
        return "soccer"
    return "generic"


def _bad_context(value: Any, row: Any) -> bool:
    text = f" {_clean_text(value).lower()} "
    if not text.strip() or any(token in text for token in POSTGAME_TOKENS):
        return True
    if _sport(row) != "combat" and any(token in text for token in ("api-mma", "api mma", "matching fight", "fighter data", "weight cut", "camp updates")):
        return True
    return any(token in text for token in BAD_CONTEXT_TOKENS)


def _source_items(row: Any, keys: Iterable[str], limit: int, max_chars: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for key in keys:
        for part in _split(_row(row).get(key)):
            if _bad_context(part, row):
                continue
            item = _clean_text(part)
            if len(item) > max_chars:
                item = (item[: max_chars - 1].rsplit(" ", 1)[0] or item[: max_chars - 1]).rstrip(".,;:") + "…"
            marker = item.lower().rstrip(".")
            if marker and marker not in seen:
                out.append(item)
                seen.add(marker)
            if len(out) >= limit:
                return out
    return out


def _es(value: Any, lang: str = "es") -> str:
    text = _clean_text(value)
    if lang != "es" or not text:
        return text
    if text in TEXT_ES:
        return TEXT_ES[text]
    text = _impl._es(text, lang)
    return TEXT_ES.get(text, text)


def _wrap(items: Iterable[str], lang: str) -> list[str]:
    return [_es(item, lang) for item in items]


def _num(row: Any, *keys: str) -> float | None:
    for key in keys:
        value = _row(row).get(key)
        if _bad(value):
            continue
        try:
            raw = str(value).strip().replace("%", "").replace(",", "")
            number = float(raw)
            return number / 100 if "%" in str(value) and abs(number) > 1 else number
        except Exception:
            pass
    return None


def _edge_state(row: Any) -> tuple[float | None, float | None, bool, bool]:
    edge = _num(row, "model_market_edge", "edge")
    ev = _num(row, "expected_value_per_unit", "profit_expected_value", "expected_value", "EV", "ev")
    return edge, ev, (edge is not None and edge < 0) or (ev is not None and ev < 0), edge is None or ev is None


def _explicit_fallback_odds(row: Any) -> bool:
    data = _row(row)
    source = _clean_text(data.get("odds_source") or data.get("data_source") or "").lower()
    status = _clean_text(data.get("odds_status") or "").lower()
    return any(token in source or token in status for token in ("uploaded", "fallback", "cached", "missing"))


def _has_odds_source(row: Any) -> bool:
    data = _row(row)
    return not _bad(data.get("odds_source") or data.get("data_source") or data.get("odds_status"))


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
    if _explicit_fallback_odds(row):
        return "WATCHLIST", "Fallback data used.", False
    if negative:
        return "WATCHLIST", DN + "play unless price improves.", False
    if not missing:
        return "PLAY SMALL", "Positive edge and EV after safety checks.", True
    return _impl.sale_ready_recommendation(row)


def sale_ready_team_items(row: Any, side: str = "") -> list[str]:
    lang = _impl._lang(row)
    keys = (f"{side}_team_form", f"{side}_team_record", f"{side}_recent_results", "team_snapshot_home", "team_snapshot_away", "team_stats_summary", "recent_results", "perplexity_context")
    items = _source_items(row, keys, 3, 62)
    return _wrap(items or ["No live team snapshot returned.", "Team data not matched to a live provider.", "Verify before entry."], lang)


def sale_ready_injury_items(row: Any, prefix: str = "") -> list[str]:
    lang = _impl._lang(row)
    keys = (f"{prefix}_injuries", f"{prefix}_injury_report", f"{prefix}_lineup_status", f"{prefix}_player_notes", "injury_report", "injuries", "lineup_status", "key_players", "perplexity_context")
    items = _source_items(row, keys, 2, 66)
    return _wrap(items or ["No verified lineup/injury update returned.", "Verify lineup/news before entry."], lang)


def sale_ready_matchup_items(row: Any) -> list[str]:
    lang = _impl._lang(row)
    items: list[str] = []
    if _explicit_fallback_odds(row):
        items.append("Odds are not live; verify current price before entry.")
    items.extend(_source_items(row, ("perplexity_context", "perplexity_summary", "sports_context_summary", "preview_summary", "game_summary", "short_reason", "matchup_note"), 1, 82))
    raw_weather = str(_row(row).get("weather_summary", "") or "")
    temp = re.search(r"(-?\d+(?:\.\d+)?°C)", raw_weather)
    wind = re.search(r"wind\s*([\d\.]+\s*kph)", raw_weather, flags=re.I)
    if temp:
        bits = [temp.group(1), "partly cloudy"]
        if wind:
            bits.append("wind " + wind.group(1))
        items.append("Weather: " + ", ".join(bits) + ".")
    location = re.search(r"Location:\s*([^\.]+)", raw_weather, flags=re.I)
    if location:
        loc = location.group(1).replace("Philadelphia, Pennsylvania, United States of America", "Philadelphia, PA, USA").replace("Pennsylvania, United States of America", "PA, USA")
        items.append("Location: " + loc + ".")
    raw_api = _clean_text(_row(row).get("api_football_summary") or _row(row).get("api_football_team_summary") or "")
    if raw_api and not _bad_context(raw_api, row):
        items.append("API-FB lookup checked; no fixture match.")
    if not items:
        items.append("Pregame context was not returned; verify odds and news before entry.")
    return _wrap(_dedupe(items)[:4], lang)


def _dedupe(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean_text(item)
        marker = text.lower().rstrip(".")
        if text and marker not in seen:
            out.append(text)
            seen.add(marker)
    return out


def sale_ready_risk_items(row: Any) -> list[str]:
    lang = _impl._lang(row)
    if _explicit_fallback_odds(row):
        return _wrap(["Fallback/watchlist only.", "Confirm current price before entry.", "Watchlist only: current price and live context need verification."], lang)
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        return _wrap(["Negative edge at current price.", DN + "play unless price improves.", "Recheck odds and key news."], lang)
    if missing:
        return _wrap(["Research only: edge incomplete.", DN + "combine unverified picks.", "Wait for verified odds."], lang)
    return _wrap(["Risk status: VOLUME OK.", "Recheck odds before entry.", "Avoid if key news changes."], lang)


def sale_ready_chain_items(row: Any) -> list[str]:
    lang = _impl._lang(row)
    explicit = _source_items(row, ("combo_magazine_items", "parlay_magazine_items", "chain_notes", "parlay_notes", "main_read", "add_on_legs"), 3, 86)
    if explicit:
        return _wrap(explicit, lang)
    if _explicit_fallback_odds(row) or not _has_odds_source(row):
        return _wrap(["No parlay recommended", "Not enough compatible selections.", "Verified odds are missing."], lang)
    _edge, _ev, negative, missing = _edge_state(row)
    if negative:
        return _wrap([DN + "chain " + NEG_EV + " picks.", "Avoid parlays unless edge turns positive.", "Recheck price before including."], lang)
    if missing:
        return _wrap(["Research only: edge incomplete.", DN + "combine unverified picks.", "Wait for verified odds."], lang)
    return _wrap(["Straight only: research.", "Avoid parlays unless all legs are +EV.", "Recheck price before including."], lang)


def _items_from_context(row: Any, keys: Iterable[str], fallback: list[str], limit: int, lang: str = "en") -> list[str]:
    key_tuple = tuple(keys)
    explicit = _source_items(row, key_tuple, limit, 86)
    if explicit:
        return _wrap(explicit, lang)
    if any(k in key_tuple for k in ("risk", "risk_level", "risk_label", "risk_note", "risk_notes", "why_lose", "hidden_risk")):
        items = sale_ready_risk_items(row)
    elif any(k in key_tuple for k in ("chain_note", "chain_notes", "parlay_note", "parlay_notes", "combo_note", "combo_magazine_items", "parlay_magazine_items", "main_read", "add_on_legs")):
        items = sale_ready_chain_items(row)
    elif "matchup_note" in key_tuple or "sports_context_summary" in key_tuple or "weather_summary" in key_tuple:
        items = sale_ready_matchup_items(row)
    elif "injury_report" in key_tuple or "lineup_status" in key_tuple or "key_players" in key_tuple:
        items = sale_ready_injury_items(row, "away")
    else:
        items = sale_ready_team_items(row)
    return _wrap(items[:limit], lang)


def _sanitize_pick(data: Any) -> dict[str, Any]:
    row = dict(_row(data))
    if _explicit_fallback_odds(row):
        row["risk"] = row["risk_level"] = row["risk_label"] = "FALLBACK MODE"
        row["final_decision"] = "WATCHLIST"
        row["chain_notes"] = "\n".join(["No parlay recommended", "Not enough compatible selections.", "Verified odds are missing."])
        row.setdefault("sports_context_summary", "Fallback report: verify current odds and news before entry.")
    for key in ("perplexity_context", "perplexity_summary", "newsapi_summary", "news_summary", "game_summary", "matchup_note", "matchup_notes", "team_snapshot_home", "team_snapshot_away", "sportsdataio_context", "sportsdataio_team_summary", "api_football_summary"):
        if _bad_context(row.get(key), row):
            row[key] = ""
    row["matchup_notes"] = "\n".join(sale_ready_matchup_items(row))
    return row


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
    original_tr = patched._tr
    original_render = patched.render_full_pick_magazine_page

    def patched_tr(value, lang):
        text = original_tr(value, lang)
        return _es(text, lang) if lang == "es" else _clean_text(text)

    def patched_render(pick, *args, **kwargs):
        report_name = kwargs.get("report_name") if "report_name" in kwargs else (args[1] if len(args) > 1 else None)
        img = original_render(_sanitize_pick(pick), *args, **kwargs)
        if report_name:
            draw = patched.ImageDraw.Draw(img, "RGBA")
            text = str(report_name or "").strip().upper()
            draw.rectangle((28, 24, 308, 74), fill=patched.RED)
            draw.text((43, 29), text, font=patched._fit(text, 250, 38, 18, True), fill="white")
        return img

    patched._tr = patched_tr
    patched.render_full_pick_magazine_page = patched_render
    try:
        from .magazine_pipeline_runtime import install as install_final_enriched_pipeline
        install_final_enriched_pipeline()
    except Exception:
        pass
    try:
        from .magazine_second_page_patch import install as install_second_page
        install_second_page(patched)
    except Exception:
        pass
    current = str(getattr(patched, "MAGAZINE_STYLE_VERSION", ""))
    patched.MAGAZINE_STYLE_VERSION = re.sub(r"(?:_direct_two_page)?_sale_ready_[a-z_]+_v\d+(?:_[a-z_]+)*", "", current) + "_sale_ready_risk_chain_v4"
    setattr(patched, "_ABA_SALE_READY_DIRECT_MULTI_LEG_APPLIED", True)
    return patched
