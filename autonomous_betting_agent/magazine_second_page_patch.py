from __future__ import annotations

from io import BytesIO
from typing import Any, Iterable
import hashlib
import re

PATCH_VERSION = "direct_second_page_v5_recommendation_board_truth_safe"
GOLD = (241, 184, 45)

ES = {
    "ADVANCED MARKET ANALYSIS": "ANÁLISIS AVANZADO DE MERCADO",
    "PAGE": "PÁGINA",
    "OF": "DE",
    "VERIFIED": "VERIFICADO",
    "VERIFY SOURCE": "VERIFICAR FUENTE",
    "HISTORY ONLY": "SOLO HISTORIAL",
    "PRICE": "CUOTA",
    "Primary Anchor": "Ancla principal",
    "Chain / Parlay Map": "Mapa Parlay / Cadena",
    "Prop / Side Market Board": "Tablero de Props / Mercados Secundarios",
    "Live Trade Triggers": "Gatillos en Vivo",
    "Flash Bets": "Apuestas Flash",
    "Hedge / Middle Notes": "Notas de Hedge / Middle",
    "Quality Gate": "Filtro de Calidad",
    "Cancel Conditions": "Condiciones de Cancelación",
    "ADVANCED MARKETS ACTIVE": "MERCADOS AVANZADOS ACTIVOS",
    "ADVANCED MARKETS NEED VERIFICATION": "MERCADOS AVANZADOS REQUIEREN VERIFICACIÓN",
    "TRIGGER-BASED WATCHLIST": "LISTA DE SEGUIMIENTO POR GATILLO",
    "MENU ONLY": "SOLO MENÚ",
    "VERIFIED RECOMMENDATION": "RECOMENDACIÓN VERIFICADA",
    "WATCHLIST": "LISTA DE SEGUIMIENTO",
    "WATCHLIST IDEA": "IDEA EN LISTA DE SEGUIMIENTO",
    "NOT RECOMMENDED": "NO RECOMENDADO",
    "+ MORE WATCHLIST IDEAS AVAILABLE": "+ MÁS IDEAS EN LISTA DE SEGUIMIENTO DISPONIBLES",
    "This page lists recommendation candidates only; unverified markets stay watchlist, trigger-based, or menu only.": "Esta página muestra candidatos de recomendación; mercados no verificados quedan como lista, gatillo o solo menú.",
}


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            return dict(data) if isinstance(data, dict) else {}
        except Exception:
            return {}
    return dict(getattr(value, "__dict__", {}) or {})


def _lang(data: dict[str, Any], language: str | None = None) -> str:
    text = _clean(language or data.get("report_language") or data.get("language") or data.get("lang")).lower()
    return "es" if text.startswith("es") or "español" in text or "espanol" in text else "en"


def _tr(value: Any, lang: str) -> str:
    text = _clean(value)
    if lang != "es":
        return text
    if text in ES:
        return ES[text]
    replacements = (
        ("Primary read", "Lectura principal"),
        ("Page one remains the official straight-bet anchor", "La página uno sigue siendo el ancla oficial de apuesta directa"),
        ("Status", "Estado"),
        ("Source", "Fuente"),
        ("Scope", "Alcance"),
        ("WATCHLIST", "LISTA DE SEGUIMIENTO"),
        ("MENU ONLY", "SOLO MENÚ"),
        ("TRIGGER-BASED", "POR GATILLO"),
        ("NOT RECOMMENDED", "NO RECOMENDADO"),
        ("VERIFIED RECOMMENDATION", "RECOMENDACIÓN VERIFICADA"),
        ("Two-leg idea", "Idea de dos selecciones"),
        ("Same-game parlay", "Parlay del mismo partido"),
        ("Team total", "Total de equipo"),
        ("First-half", "Primer tiempo"),
        ("Second-half", "Segundo tiempo"),
        ("next score", "próximo anotador/equipo"),
        ("favorite scores first", "favorito anota primero"),
        ("underdog scores first", "no favorito anota primero"),
        ("halftime", "medio tiempo"),
        ("hedge", "hedge"),
        ("middle", "middle"),
        ("cashout", "cashout"),
        ("Cancel", "Cancelar"),
        ("Verify", "Verificar"),
        ("requires", "requiere"),
        ("price", "cuota"),
        ("line", "línea"),
        ("market", "mercado"),
        ("context", "contexto"),
    )
    for old, new in replacements:
        text = re.sub(re.escape(old), new, text, flags=re.I)
    return text


def _get(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        text = _clean(data.get(key))
        if text and text.lower() not in {"nan", "none", "null", "n/a", "na", "--", "data unavailable"}:
            return text
    return default


def _split(value: Any) -> list[str]:
    text = str(value or "").replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [_clean(part).strip(" -•") for part in text.splitlines() if _clean(part).strip(" -•")]


def _decimal_text(value: Any) -> str | None:
    raw = _clean(value).replace("−", "-").replace("–", "-").replace("—", "-").replace(",", "")
    if not raw:
        return None
    try:
        num = float(raw)
    except Exception:
        return None
    if num <= -100:
        num = 1.0 + 100.0 / abs(num)
    elif num >= 100:
        num = 1.0 + num / 100.0
    elif num <= 1:
        return None
    return f"{num:.2f}"


def _ok(data: dict[str, Any]) -> bool:
    status = _get(data, "odds_status", "odds_api_status").lower()
    flag = _get(data, "odds_api_live", "the_odds_api_live", "odds_verified").lower()
    mode = _get(data, "report_source_mode").lower()
    return mode == "current-run" and (status in {"live", "live_match", "live_api", "odds_api_live_match"} or flag in {"1", "true", "yes", "live", "verified"})


def _source_status(data: dict[str, Any], lang: str) -> tuple[str, tuple[int, int, int]]:
    mode = _get(data, "report_source_mode").lower()
    if mode == "ledger-history":
        return _tr("HISTORY ONLY", lang), GOLD
    if _ok(data):
        return _tr("VERIFIED", lang), (61, 205, 84)
    return _tr("VERIFY SOURCE", lang), GOLD


def _field_items(data: dict[str, Any], keys: tuple[str, ...], fallback: list[str], lang: str, limit: int = 4) -> list[str]:
    out: list[str] = []
    for key in keys:
        out.extend(_split(data.get(key)))
    out = [item for item in out if not any(token in item.lower() for token in ("not returned", "data unavailable", "context unavailable", "api key missing"))]
    return [_tr(item, lang) for item in (out or fallback)[:limit]]


def _source_rows(data: dict[str, Any], lang: str) -> list[str]:
    return [
        _tr("Source: ", lang) + _tr(_get(data, "report_source_label", "report_source_mode", default="VERIFY"), lang),
        _tr("Scope: ", lang) + _tr(_get(data, "report_data_scope", default="VERIFY"), lang),
        _tr("Status: ", lang) + _tr(_get(data, "report_truth_severity", "verification_status", default="VERIFY SOURCE"), lang),
    ]


def _status_prefix(data: dict[str, Any]) -> str:
    return "VERIFIED RECOMMENDATION" if _ok(data) else "WATCHLIST"


def _chain_rows(data: dict[str, Any], lang: str) -> list[str]:
    status = _status_prefix(data)
    fallback = [
        f"{status} · Two-leg idea: anchor + alternate total only after event and line match.",
        "MENU ONLY · Same-game parlay: anchor + team total if book confirms both markets.",
        "WATCHLIST IDEA · Correlated angle: anchor + second-half total after pace confirmation.",
        "NOT RECOMMENDED · Avoid aggressive multi-leg chains until price gate passes.",
    ]
    return _field_items(data, ("advanced_chain_ideas", "correlated_markets", "add_on_legs", "parlay_notes"), fallback, lang, 4)


def _prop_rows(data: dict[str, Any], lang: str) -> list[str]:
    fallback = [
        "MENU ONLY · Team total: compare projected tempo with live team total before entry.",
        "MENU ONLY · Game total alternate line: wait for a better number than fair price.",
        "TRIGGER-BASED · Team to qualify / next score only if live price beats target.",
        "WATCHLIST IDEA · Corners, throw-ins, free kicks, shots only when book and context support them.",
    ]
    return _field_items(data, ("prop_market_ideas", "side_market_ideas", "prop_market_notes", "advanced_market_notes", "team_to_qualify_angle", "next_score_angle", "corners_angle", "throw_ins_angle", "free_kicks_angle"), fallback, lang, 4)


def _live_rows(data: dict[str, Any], lang: str) -> list[str]:
    fallback = [
        "TRIGGER-BASED · If favorite scores first, watch alternate total and hedge price.",
        "TRIGGER-BASED · If underdog scores first, watch favorite live moneyline drift.",
        "TRIGGER-BASED · If tied at halftime, watch second-half total and next score.",
        "TRIGGER-BASED · If tempo/pressure rises, watch short-window totals or pressure markets.",
    ]
    return _field_items(data, ("live_trade_triggers", "live_betting_notes", "minute_window_angles", "in_game_notes"), fallback, lang, 4)


def _flash_rows(data: dict[str, Any], lang: str) -> list[str]:
    fallback = [
        "TRIGGER-BASED · Next team to score after pressure spike; cancel if momentum fades.",
        "TRIGGER-BASED · Short-window total after two sustained attacks or price drop.",
        "MENU ONLY · Live alternate total if market overreacts to slow early pace.",
        "WATCHLIST IDEA · Momentum trade only inside the valid timing window.",
    ]
    return _field_items(data, ("flash_bets", "flash_market_notes"), fallback, lang, 4)


def _hedge_rows(data: dict[str, Any], lang: str) -> list[str]:
    fallback = [
        "WATCHLIST IDEA · Hedge only after a favorable score state, not from fear.",
        "MENU ONLY · Middle becomes possible only after line moves across the original number.",
        "WATCHLIST IDEA · Cashout only if price no longer beats fair value.",
        "NOT RECOMMENDED · Do not chase if the trigger window expires.",
    ]
    return _field_items(data, ("hedge_notes", "middle_notes", "cashout_notes"), fallback, lang, 4)


def _quality_rows(data: dict[str, Any], lang: str) -> list[str]:
    status, _color = _source_status(data, lang)
    fallback = [
        "Source gate: " + status,
        "Price gate: requires current price above target price.",
        "Value gate: requires positive EV and edge.",
        "Market gate: requires exact event, market, line, and selection match.",
    ]
    return _field_items(data, ("quality_gate_notes",), fallback, lang, 4)


def _cancel_rows(data: dict[str, Any], lang: str) -> list[str]:
    fallback = [
        "Cancel if live odds cannot be matched to the same event.",
        "Cancel if price moves below fair value or target price.",
        "Cancel if lineup/news/weather context changes materially.",
        "Cancel if tempo does not match the trigger condition.",
        "+ MORE WATCHLIST IDEAS AVAILABLE",
    ]
    return _field_items(data, ("do_not_bet_conditions", "cancel_conditions", "risk_notes"), fallback, lang, 5)


def _page_two_sections(data: dict[str, Any], lang: str) -> list[tuple[str, list[str], tuple[int, int, int]]]:
    pick = _get(data, "prediction", "exact_bet", "pick", "selection", default="Primary pick")
    anchor = [
        "Primary read: " + pick + ".",
        "Page one remains the official straight-bet anchor.",
        *_source_rows(data, lang),
    ]
    return [
        ("Primary Anchor", [_tr(item, lang) for item in anchor[:4]], (190, 30, 28)),
        ("Chain / Parlay Map", _chain_rows(data, lang), (19, 66, 108)),
        ("Prop / Side Market Board", _prop_rows(data, lang), (19, 66, 108)),
        ("Live Trade Triggers", _live_rows(data, lang), GOLD),
        ("Flash Bets", _flash_rows(data, lang), GOLD),
        ("Hedge / Middle Notes", _hedge_rows(data, lang), (19, 66, 108)),
        ("Quality Gate", _quality_rows(data, lang), (190, 30, 28)),
        ("Cancel Conditions", _cancel_rows(data, lang), (190, 30, 28)),
    ]


def _png(image: Any) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _draw_second_page(module: Any, pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 2, total_pages: int = 2, language: str | None = None):
    from PIL import ImageDraw
    data = _row(pick)
    lang = _lang(data, language)
    black = getattr(module, "BLACK", (13, 14, 16))
    red = getattr(module, "RED", (190, 30, 28))
    blue = getattr(module, "BLUE", (19, 66, 108))
    cream = getattr(module, "CREAM", (255, 248, 230))
    paper = getattr(module, "PAPER", (244, 235, 211))
    seed = int(hashlib.sha256((_get(data, "event", "game", "matchup", "event_name", default="advanced") + "page2").encode()).hexdigest()[:8], 16)
    img = module._paper(seed).convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    draw.rectangle((18, 18, 1062, 82), fill=black)
    draw.rectangle((28, 24, 308, 74), fill=red)
    draw.text((43, 29), "ABA SIGNAL PRO", font=module._fit("ABA SIGNAL PRO", 250, 38, 25, True), fill="white")
    title = _tr("ADVANCED MARKET ANALYSIS", lang)
    draw.text((330, 28), title, font=module._fit(title, 500, 34, 15, True), fill="white")
    page_text = f"{_tr('PAGE', lang)} {page_number} {_tr('OF', lang)} {total_pages}"
    draw.rounded_rectangle((840, 24, 1050, 74), radius=5, fill=cream, outline=black)
    draw.text((862, 32), page_text, font=module._fit(page_text, 174, 28, 16, True), fill=black)

    away, home = module._teams(data)
    matchup = f"{away} vs {home}".upper()
    module._txt_auto(draw, 42, 104, matchup, 660, 58, 52, 16, red, True, 2)
    pick_text = _tr(module._pick(data).upper(), lang)
    module._txt_auto(draw, 42, 172, pick_text, 650, 42, 36, 14, blue, True, 2)

    status, status_color = _source_status(data, lang)
    draw.rounded_rectangle((720, 104, 1042, 222), radius=14, fill=black, outline=status_color, width=3)
    draw.text((740, 122), status, font=module._fit(status, 282, 25, 11, True), fill=status_color)
    price = _decimal_text(_get(data, "display_decimal_odds", "decimal_price", "decimal_odds", "odds", "best_price", "odds_at_pick", "american_odds", "odds_american")) or "N/A"
    price_text = f"{_tr('PRICE', lang)} {price}"
    draw.text((740, 163), price_text, font=module._fit(price_text, 250, 30, 13, True), fill=cream)

    note = _get(data, "report_truth_warning", default="This page lists recommendation candidates only; unverified markets stay watchlist, trigger-based, or menu only.")
    draw.rounded_rectangle((42, 246, 1042, 312), radius=12, fill=GOLD + (245,), outline=black, width=2)
    module._txt_auto(draw, 64, 263, _tr(note, lang), 956, 34, 21, 9, black, True, 2)

    def box(x: int, y: int, w: int, h: int, title: str, rows: list[str], color: tuple[int, int, int], row_limit: int = 4) -> None:
        draw.rounded_rectangle((x, y, x + w, y + h), radius=14, fill=paper + (255,), outline=black + (220,), width=3)
        draw.rounded_rectangle((x, y, x + w, y + 48), radius=10, fill=color)
        label = _tr(title, lang).upper()
        draw.text((x + 14, y + 9), label, font=module._fit(label, w - 28, 25, 10, True), fill=cream)
        cy = y + 62
        font_start = 15 if h <= 218 else 16
        for item in rows[:row_limit]:
            if cy > y + h - 28:
                break
            draw.ellipse((x + 15, cy + 5, x + 27, cy + 17), fill=color)
            module._txt_auto(draw, x + 36, cy, _tr(item, lang), w - 50, 38, font_start, 7, black, False, 2)
            cy += 42

    sections = _page_two_sections(data, lang)
    coords = [
        (42, 336, 488, 218),
        (552, 336, 488, 218),
        (42, 574, 488, 238),
        (552, 574, 488, 238),
        (42, 832, 488, 238),
        (552, 832, 488, 238),
        (42, 1090, 488, 238),
        (552, 1090, 488, 238),
    ]
    for (title, rows, color), (x, y, w, h) in zip(sections, coords):
        box(x, y, w, h, title, rows, color, 5 if title == "Cancel Conditions" else 4)

    draw.rounded_rectangle((42, 1352, 1042, 1518), radius=16, fill=black, outline=status_color, width=4)
    verdict = _tr("ADVANCED MARKETS ACTIVE" if _ok(data) else "ADVANCED MARKETS NEED VERIFICATION", lang)
    draw.text((68, 1375), verdict, font=module._fit(verdict, 914, 40, 15, True), fill=status_color)
    final = "Verified markets may be used only when source, price, value, market, context, and execution gates all pass."
    if not _ok(data):
        final = "No fake verified props/parlays/live trades. Use these as menu-only, watchlist, or trigger-based candidates until source match is confirmed."
    module._txt_auto(draw, 68, 1432, _tr(final, lang), 914, 56, 22, 8, cream, False, 2)
    draw.rectangle((20, 1542, 1060, 1581), fill=black)
    module._txt_auto(draw, 42, 1550, getattr(module, "SAFETY_FOOTER", "Informational only."), 890, 20, 15, 8, cream, False, 1)
    return img.convert("RGB")


def install(module: Any | None = None) -> Any:
    if module is None:
        try:
            import autonomous_betting_agent.magazine_book_export as module
        except Exception:
            return None
    if getattr(module, "_ABA_DIRECT_SECOND_PAGE_PATCH", "") == PATCH_VERSION:
        return module
    try:
        module.ES.update(ES)
    except Exception:
        pass
    original_fmt = getattr(module, "_fmt", None)
    if callable(original_fmt) and not getattr(original_fmt, "_ABA_DECIMAL_ODDS_DIRECT", False):
        def fmt_decimal_first(value: Any, kind: str = "") -> str:
            if kind == "odds":
                decimal = _decimal_text(value)
                if decimal:
                    return decimal
            return original_fmt(value, kind)
        fmt_decimal_first._ABA_DECIMAL_ODDS_DIRECT = True  # type: ignore[attr-defined]
        module._fmt = fmt_decimal_first
    original_page_png = getattr(module, "render_full_pick_magazine_page_png", None)
    if callable(original_page_png):
        def two_page_png(pick: Any, background_image: Any = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
            page_total = max(2, int(total_pages or 1) * 2)
            first = max(1, int(page_number or 1) * 2 - 1)
            page_one = module.render_full_pick_magazine_page(pick, background_image, report_name, first, page_total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
            page_two = _draw_second_page(module, pick, background_image, report_name, first + 1, page_total, language)
            from PIL import Image
            book = Image.new("RGB", (page_one.width, page_one.height * 2), getattr(module, "PAPER", (244, 235, 211)))
            book.paste(page_one.convert("RGB"), (0, 0))
            book.paste(page_two.convert("RGB"), (0, page_one.height))
            return _png(book)
        two_page_png._ABA_TWO_PAGE_DIRECT = True  # type: ignore[attr-defined]
        module.render_full_pick_magazine_page_png = two_page_png
    def render_pages(picks: Iterable[Any], background_image: Any = None, report_name: str | None = None, logo_image: Any = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> list[Any]:
        rows = list(picks) or [{"event": "No Picks", "prediction": "NO PICK"}]
        total = len(rows) * 2
        pages: list[Any] = []
        for index, row in enumerate(rows):
            pages.append(module.render_full_pick_magazine_page(row, background_image, report_name, index * 2 + 1, total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))
            pages.append(_draw_second_page(module, row, background_image, report_name, index * 2 + 2, total, language))
        return pages
    module.render_full_magazine_book_pages = render_pages
    module._ABA_DIRECT_SECOND_PAGE_PATCH = PATCH_VERSION
    if "direct_two_page" not in str(getattr(module, "MAGAZINE_STYLE_VERSION", "")):
        module.MAGAZINE_STYLE_VERSION = f"{getattr(module, 'MAGAZINE_STYLE_VERSION', 'magazine')}_direct_two_page"
    return module


install()
