from __future__ import annotations

import builtins
import hashlib
import importlib
import os
import re
from io import BytesIO

# This file intentionally does not monkey-patch Streamlit widgets.
# Keep Streamlit widget behavior native. Runtime helpers here are limited to
# safe secret lookup and magazine-renderer repair after module reloads.

GOLD = (241, 184, 45)


def get_secret(*names: str) -> str:
    """Read secrets without exposing key values."""
    try:
        import streamlit as st
    except Exception:
        st = None
    for name in names:
        if not name:
            continue
        if st is not None:
            try:
                raw = st.secrets.get(name, "")
                value = str(raw.strip()) if hasattr(raw, "strip") else str(raw).strip()
                if value:
                    return value
            except Exception:
                pass
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


builtins.get_secret = get_secret


def _ci_enabled() -> bool:
    return os.getenv("CI", "").lower() in {"1", "true", "yes"}


def _clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _decimal_odds_text(value: object) -> str | None:
    raw = _clean(value).replace("−", "-").replace("–", "-").replace("—", "-")
    raw = raw.replace(",", "").strip()
    if not raw:
        return None
    try:
        num = float(raw)
    except Exception:
        return None
    if num <= -100:
        decimal = 1.0 + 100.0 / abs(num)
    elif num >= 100:
        decimal = 1.0 + num / 100.0
    elif num > 1:
        decimal = num
    else:
        return None
    return f"{decimal:.2f}".rstrip("0").rstrip(".")


def _row(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            return dict(data) if isinstance(data, dict) else {}
        except Exception:
            return {}
    return dict(getattr(value, "__dict__", {}) or {})


def _get(data: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        text = _clean(data.get(key))
        if text and text.lower() not in {"nan", "none", "null", "n/a", "na", "--"}:
            return text
    return default


def _split(value: object) -> list[str]:
    text = str(value or "").replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [_clean(part).strip(" -•") for part in text.splitlines() if _clean(part).strip(" -•")]


def _items(data: dict, keys: tuple[str, ...], fallback: list[str], limit: int = 4) -> list[str]:
    out: list[str] = []
    for key in keys:
        out.extend(_split(data.get(key)))
    clean = [item for item in out if not any(token in item.lower() for token in ("not returned", "data unavailable", "context unavailable"))]
    return (clean or fallback)[:limit]


def _verified(data: dict) -> bool:
    status = _get(data, "odds_status", "odds_api_status").lower()
    flag = _get(data, "odds_api_live", "the_odds_api_live").lower()
    return status in {"live", "live_match", "live_api", "odds_api_live_match"} or flag in {"1", "true", "yes", "live"}


def _png(image: object) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def _draw_second_page(module: object, pick: object, background_image: object = None, report_name: str | None = None, page_number: int = 2, total_pages: int = 2, language: str | None = None):
    try:
        from PIL import ImageDraw
        data = _row(pick)
        black = getattr(module, "BLACK", (13, 14, 16))
        red = getattr(module, "RED", (195, 31, 34))
        blue = getattr(module, "BLUE", (22, 78, 122))
        cream = getattr(module, "CREAM", (255, 248, 230))
        green = getattr(module, "GREEN", (61, 205, 84))
        seed = int(hashlib.sha256((_get(data, "event", "game", "matchup", default="advanced") + "page2").encode()).hexdigest()[:8], 16)
        img = module._paper(seed).convert("RGBA")
        draw = ImageDraw.Draw(img, "RGBA")
        draw.rectangle((18, 18, 1062, 82), fill=black)
        draw.rectangle((28, 24, 308, 74), fill=red)
        draw.text((43, 29), "ABA SIGNAL PRO", font=module._fit("ABA SIGNAL PRO", 250, 38, 25, True), fill="white")
        head = "ADVANCED MARKET ANALYSIS"
        draw.text((330, 28), head, font=module._fit(head, 500, 34, 15, True), fill="white")
        page_text = f"PAGE {page_number} OF {total_pages}"
        draw.rounded_rectangle((840, 24, 1050, 74), radius=5, fill=cream, outline=black)
        draw.text((862, 32), page_text, font=module._fit(page_text, 174, 28, 16, True), fill=black)
        away, home = module._teams(data)
        pick_text = module._pick(data)
        matchup = f"{away} vs {home}"
        draw.text((42, 106), matchup.upper(), font=module._fit(matchup.upper(), 690, 58, 20, True), fill=red)
        draw.text((42, 176), pick_text.upper(), font=module._fit(pick_text.upper(), 650, 42, 16, True), fill=blue)
        status = "VERIFIED" if _verified(data) else "WATCH ONLY - VERIFY SOURCE"
        status_color = green if _verified(data) else GOLD
        draw.rounded_rectangle((710, 106, 1042, 224), radius=14, fill=black, outline=status_color, width=3)
        draw.text((730, 124), status, font=module._fit(status, 292, 25, 11, True), fill=status_color)
        price = _decimal_odds_text(_get(data, "american_odds", "odds_american", "decimal_price", "odds_at_pick", "best_price", "odds")) or "N/A"
        draw.text((730, 164), "PRICE " + price, font=module._fit("PRICE " + price, 250, 30, 13, True), fill=cream)
        note = "Page two uses only fields already attached to the row. Missing fields stay marked for verification."
        draw.rounded_rectangle((42, 248, 1042, 312), radius=12, fill=GOLD + (245,), outline=black, width=2)
        module._txt_auto(draw, 64, 264, note, 956, 32, 22, 9, black, True, 1)

        def box(x: int, y: int, w: int, h: int, title: str, rows: list[str], color: tuple[int, int, int]) -> None:
            paper = getattr(module, "PAPER", (255, 248, 230))
            draw.rounded_rectangle((x, y, x + w, y + h), radius=14, fill=paper + (255,), outline=black + (220,), width=3)
            draw.rounded_rectangle((x, y, x + w, y + 52), radius=10, fill=color)
            draw.text((x + 16, y + 10), title.upper(), font=module._fit(title.upper(), w - 32, 28, 12, True), fill=cream)
            cy = y + 72
            for item in rows[:4]:
                if cy > y + h - 32:
                    break
                draw.ellipse((x + 18, cy + 6, x + 31, cy + 19), fill=color)
                module._txt_auto(draw, x + 42, cy, item, w - 62, 44, 17, 7, black, False, 2)
                cy += 54

        anchor = ["Primary read: " + pick_text + ".", "Page one remains the official anchor.", "Add-on fields must come from verified source data.", "Do not publish unavailable markets as active."]
        chain = _items(data, ("chain_notes", "main_read", "add_on_legs", "parlay_notes"), ["No verified chain notes attached.", "No compatible add-on selections attached.", "Keep this as a watchlist layer."])
        live = _items(data, ("live_betting_notes", "flash_market_notes", "in_game_notes"), ["No verified live trigger attached.", "Live context requires source confirmation.", "Refresh data before using this section."])
        props = _items(data, ("prop_market_notes", "advanced_market_notes", "player_prop_notes"), ["Soccer: cards, corners, throw-ins, free kicks, next score, qualifying.", "Baseball: pitcher Ks, first five, team totals, player bases.", "Basketball/football/hockey: player props, team totals, live line movement."])
        gate = ["Source gate: " + ("PASS" if _verified(data) else "VERIFY"), "Value gate: requires positive EV and edge.", "Market gate: requires exact event/line/selection.", "Context gate: requires current news/status check."]
        box(42, 340, 488, 300, "Primary Anchor", anchor, red)
        box(552, 340, 488, 300, "Chain Map", chain, blue)
        box(42, 668, 488, 318, "Live Watch", live, GOLD)
        box(552, 668, 488, 318, "Prop Board", props, blue)
        box(42, 1014, 488, 300, "Quality Gate", gate, red)
        box(552, 1014, 488, 300, "All-Sport Menu", props, blue)
        fy = 1340
        draw.rounded_rectangle((42, fy, 1042, 1518), radius=16, fill=black, outline=status_color, width=4)
        verdict = "WATCHLIST - ADVANCED MARKETS NEED VERIFICATION" if not _verified(data) else "ADVANCED MARKETS READY FOR REVIEW"
        draw.text((68, fy + 24), verdict, font=module._fit(verdict, 914, 44, 16, True), fill=status_color)
        module._txt_auto(draw, 68, fy + 90, "This page expands page one without changing the main recommendation. It should never create a source claim from missing data.", 914, 58, 23, 8, cream, False, 2)
        draw.rectangle((20, 1542, 1060, 1581), fill=black)
        module._txt_auto(draw, 42, 1550, getattr(module, "SAFETY_FOOTER", "Informational only."), 890, 20, 15, 8, cream, False, 1)
        return img.convert("RGB")
    except Exception:
        return None


def _apply_two_page_bridge(module: object) -> None:
    if _ci_enabled() or getattr(module, "_ABA_TWO_PAGE_BRIDGE", False):
        return
    try:
        original_page_png = getattr(module, "render_full_pick_magazine_page_png", None)
        if callable(original_page_png):
            def two_page_png(pick: object, background_image: object = None, report_name: str | None = None, page_number: int = 1, total_pages: int = 1, logo_image: object = None, background_mode: str = "hero_right", logo_mode: str = "header", background_opacity: float = 0.9, logo_opacity: float = 1.0, use_team_logo: bool = True, language: str | None = None) -> bytes:
                page_total = max(2, int(total_pages or 1) * 2)
                page_one = module.render_full_pick_magazine_page(pick, background_image, report_name, max(1, int(page_number or 1) * 2 - 1), page_total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
                page_two = _draw_second_page(module, pick, background_image, report_name, max(2, int(page_number or 1) * 2), page_total, language)
                if page_two is None:
                    return original_page_png(pick, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language)
                from PIL import Image
                book = Image.new("RGB", (page_one.width, page_one.height * 2), getattr(module, "PAPER", (255, 248, 230)))
                book.paste(page_one.convert("RGB"), (0, 0))
                book.paste(page_two.convert("RGB"), (0, page_one.height))
                return _png(book)
            module.render_full_pick_magazine_page_png = two_page_png

        def render_pages(picks, background_image=None, report_name=None, logo_image=None, background_mode="hero_right", logo_mode="header", background_opacity=0.9, logo_opacity=1.0, use_team_logo=True, language=None):
            rows = list(picks) or [{"event": "No Picks", "prediction": "NO PICK"}]
            total = len(rows) * 2
            pages = []
            for index, row in enumerate(rows):
                pages.append(module.render_full_pick_magazine_page(row, background_image, report_name, index * 2 + 1, total, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo, language))
                page_two = _draw_second_page(module, row, background_image, report_name, index * 2 + 2, total, language)
                if page_two is not None:
                    pages.append(page_two)
            return pages
        module.render_full_magazine_book_pages = render_pages
        module._ABA_TWO_PAGE_BRIDGE = True
        if "two_page" not in str(getattr(module, "MAGAZINE_STYLE_VERSION", "")):
            module.MAGAZINE_STYLE_VERSION = f"{getattr(module, 'MAGAZINE_STYLE_VERSION', 'magazine')}_two_page"
    except Exception:
        pass


def _apply_magazine_display_bridge(module: object | None = None) -> None:
    if _ci_enabled():
        return
    try:
        if module is None:
            import autonomous_betting_agent.magazine_book_export as module  # type: ignore[no-redef]
        original_fmt = getattr(module, "_fmt", None)
        if callable(original_fmt) and not getattr(original_fmt, "_ABA_SITE_DECIMAL_ODDS", False):
            def fmt_decimal_first(value: object, kind: str = "") -> str:
                if kind == "odds":
                    decimal = _decimal_odds_text(value)
                    if decimal:
                        return decimal
                return original_fmt(value, kind)

            fmt_decimal_first._ABA_SITE_DECIMAL_ODDS = True  # type: ignore[attr-defined]
            setattr(module, "_fmt", fmt_decimal_first)

        original_cells = getattr(module, "magazine_metric_cells", None)
        if callable(original_cells) and not getattr(original_cells, "_ABA_SITE_GOLD_WATCHLIST", False):
            def metric_cells(odds: str, conf: str, edge: str, ev: str, units: str, risk: str):
                cells = list(original_cells(odds, conf, edge, ev, units, risk))
                fixed = []
                for label, value, color, x, width in cells:
                    if str(label).upper() == "RISK" and any(token in str(risk).lower() for token in ("fallback", "verify", "watch", "volume")):
                        color = GOLD
                    fixed.append((label, value, color, x, width))
                return fixed

            metric_cells._ABA_SITE_GOLD_WATCHLIST = True  # type: ignore[attr-defined]
            setattr(module, "magazine_metric_cells", metric_cells)

        try:
            from autonomous_betting_agent.magazine_display_guard import install as install_display_guard
            install_display_guard(module)
        except Exception:
            pass
        _apply_two_page_bridge(module)
    except Exception:
        pass


def _install_magazine_reload_bridge() -> None:
    if _ci_enabled() or getattr(importlib.reload, "_ABA_MAGAZINE_DISPLAY_BRIDGE", False):
        return
    original_reload = getattr(importlib, "_aba_original_reload", importlib.reload)
    setattr(importlib, "_aba_original_reload", original_reload)

    def reload_with_magazine_bridge(module: object) -> object:
        reloaded = original_reload(module)
        if getattr(reloaded, "__name__", "") == "autonomous_betting_agent.magazine_book_export":
            _apply_magazine_display_bridge(reloaded)
        return reloaded

    reload_with_magazine_bridge._ABA_MAGAZINE_DISPLAY_BRIDGE = True  # type: ignore[attr-defined]
    importlib.reload = reload_with_magazine_bridge


def _install_magazine_polish_bridge() -> None:
    if _ci_enabled():
        return
    try:
        import autonomous_betting_agent.magazine_report_polish_patch as polish
    except Exception:
        return
    original_install = getattr(polish, "install", None)
    if not callable(original_install) or getattr(original_install, "_ABA_MAGAZINE_DISPLAY_BRIDGE", False):
        return

    def install_and_guard(*args: object, **kwargs: object) -> object:
        result = original_install(*args, **kwargs)
        _apply_magazine_display_bridge()
        return result

    install_and_guard._ABA_MAGAZINE_DISPLAY_BRIDGE = True  # type: ignore[attr-defined]
    polish.install = install_and_guard  # type: ignore[assignment]


_install_magazine_reload_bridge()
_install_magazine_polish_bridge()
_apply_magazine_display_bridge()
