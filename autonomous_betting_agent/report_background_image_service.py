from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from textwrap import wrap
from typing import Any, Mapping

import pandas as pd
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .report_learning_layer_compat import apply_learning_layer_compat
from .report_product_layer import MagazineBrand, safe_float, safe_text

PNG_HEADER = b"\x89PNG\r\n\x1a\n"
PNG_RENDERER_VERSION = "client-ready-png-v3"
PAGE_W = 1080
PAGE_H = 1350
INK = (255, 255, 255)
MUTED = (236, 241, 250)
GOLD = (255, 210, 72)
GREEN = (125, 245, 180)
PANEL_RGB = (6, 10, 18)
BORDER = (255, 255, 255)
DEFAULT_BG = (38, 48, 70)


def _font(size: int = 42):
    for name in ("DejaVuSerif.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _bold(size: int = 42):
    for name in ("DejaVuSerif-Bold.ttf", "DejaVuSans-Bold.ttf", "DejaVuSerif.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _brand_value(brand: MagazineBrand | Mapping[str, Any] | None, key: str, default: str) -> str:
    if isinstance(brand, Mapping):
        return safe_text(brand.get(key)) or default
    if brand is not None:
        return safe_text(getattr(brand, key, "")) or default
    return default


def _has_background(background_bytes: bytes | None) -> bool:
    return bool(background_bytes)


def _background(background_bytes: bytes | None) -> Image.Image:
    has_custom = _has_background(background_bytes)
    if has_custom:
        try:
            src = Image.open(BytesIO(background_bytes or b"")).convert("RGB")
        except Exception:
            src = Image.new("RGB", (PAGE_W, PAGE_H), DEFAULT_BG)
            has_custom = False
    else:
        src = Image.new("RGB", (PAGE_W, PAGE_H), DEFAULT_BG)
    scale = max(PAGE_W / src.width, PAGE_H / src.height)
    resized = src.resize((int(src.width * scale), int(src.height * scale)))
    left = max(0, (resized.width - PAGE_W) // 2)
    top = max(0, (resized.height - PAGE_H) // 2)
    canvas = resized.crop((left, top, left + PAGE_W, top + PAGE_H))
    if has_custom:
        canvas = ImageEnhance.Color(canvas).enhance(1.08)
        canvas = ImageEnhance.Brightness(canvas).enhance(1.03)
        return canvas.convert("RGB")
    canvas = ImageEnhance.Color(canvas).enhance(0.82)
    canvas = ImageEnhance.Brightness(canvas).enhance(0.82)
    return canvas.filter(ImageFilter.GaussianBlur(radius=0.35)).convert("RGB")


def _png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.convert("RGB").save(out, format="PNG", optimize=False)
    return out.getvalue()


def _measure(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=font)
    return box[2] - box[0], box[3] - box[1]


def _center(draw: ImageDraw.ImageDraw, y: int, text: str, font, fill=INK) -> int:
    w, h = _measure(draw, text, font)
    draw.text(((PAGE_W - w) // 2, y), text, font=font, fill=fill)
    return y + h


def _wrapped(draw: ImageDraw.ImageDraw, x: int, y: int, text: Any, font, *, width: int = 34, fill=INK, max_lines: int = 5, line_gap: int = 10) -> int:
    lines = wrap(safe_text(text), width=width)[:max_lines] or ["N/A"]
    step = _measure(draw, "Ag", font)[1] + line_gap
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += step
    return y


def _panel(image: Image.Image, box: tuple[int, int, int, int], *, radius: int = 28, alpha: int = 150, outline_alpha: int = 185, width: int = 2) -> None:
    overlay = Image.new("RGBA", (PAGE_W, PAGE_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    fill = (*PANEL_RGB, alpha)
    outline = (*BORDER, outline_alpha)
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)
    image.paste(Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB"))


def _scrim(image: Image.Image, *, alpha: int = 35) -> None:
    overlay = Image.new("RGBA", (PAGE_W, PAGE_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay, "RGBA")
    draw.rectangle((0, 0, PAGE_W, PAGE_H), fill=(0, 0, 0, alpha))
    image.paste(Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB"))


def _pct(value: Any, *, signed: bool = False) -> str:
    number = safe_float(value)
    if number is None:
        return "N/A"
    if abs(number) <= 1.5:
        number *= 100
    return f"{number:+.1f}%" if signed else f"{number:.1f}%"


def _price(value: Any) -> str:
    number = safe_float(value)
    return f"{number:.2f}" if number is not None else "N/A"


def _first(row: Mapping[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = safe_text(row.get(name))
        if value:
            return value
    return ""


def _trend(row: Mapping[str, Any]) -> str:
    return _first(row, ("public_pick", "prediction", "tendency", "consumer_action")) or "Research / Learning"


def _action(row: Mapping[str, Any]) -> str:
    return _first(row, ("consumer_action", "recommended_action", "official_status_label", "price_value_label")) or "Research / Learning"


def _reason(row: Mapping[str, Any]) -> str:
    for field in ("sports_context_summary", "market_read", "why_it_matters", "game_preview", "learning_status", "data_issue_reason"):
        text = safe_text(row.get(field))
        if text and "unavailable" not in text.lower():
            return text
    return "Price, model, and proof gates reviewed. This stays research unless it passes official +EV rules."


def _metrics(row: Mapping[str, Any]) -> list[str]:
    parts: list[str] = []
    sport = _first(row, ("public_sport", "sport", "league"))
    if sport:
        parts.append(sport[:18])
    confidence = _first(row, ("confidence_tier", "confidence", "model_lean_label"))
    if confidence:
        parts.append(f"Conf: {confidence[:14]}")
    price = _price(row.get("decimal_price") or row.get("best_price") or row.get("odds_decimal"))
    if price != "N/A":
        parts.append(f"Price: {price}")
    model = _pct(row.get("model_probability") or row.get("learned_model_probability"))
    if model != "N/A":
        parts.append(f"Model: {model}")
    market = _pct(row.get("market_probability"))
    if market != "N/A":
        parts.append(f"Market: {market}")
    edge = _pct(row.get("model_market_edge"), signed=True)
    if edge != "N/A":
        parts.append(f"Edge: {edge}")
    ev = _pct(row.get("expected_value_per_unit"), signed=True)
    if ev != "N/A":
        parts.append(f"EV: {ev}")
    return parts[:5]


def _summary_counts(cards: pd.DataFrame) -> tuple[int, int, int, int]:
    total = int(len(cards))
    official = int(cards.get("official_publish_ready", pd.Series(dtype=bool)).fillna(False).astype(bool).sum()) if not cards.empty else 0
    lane = cards.get("report_lane_v2", cards.get("report_lane", pd.Series(dtype=str))).fillna("").astype(str).str.lower() if not cards.empty else pd.Series(dtype=str)
    research = int(lane.str.contains("research|watch|no_play|no play", regex=True).sum()) if not lane.empty else max(total - official, 0)
    issues = int(cards.get("data_issue_reason", pd.Series(dtype=str)).fillna("").astype(str).ne("").sum()) if not cards.empty else 0
    return total, official, research, issues


def render_custom_background_card_png(row: Mapping[str, Any], brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, index: int = 0) -> bytes:
    row = dict(row or {})
    has_custom = _has_background(background_bytes)
    image = _background(background_bytes)
    if not has_custom:
        _scrim(image, alpha=80)
    draw = ImageDraw.Draw(image)
    brand_name = _brand_value(brand, "brand_name", "ABA Signal Pro")
    title = safe_text(row.get("event") or row.get("matchup")) or "Matchup"
    sport = _first(row, ("sport", "public_sport", "league")) or "Sports"
    action = _action(row)
    _panel(image, (54, 54, PAGE_W - 54, PAGE_H - 54), radius=38, alpha=105 if has_custom else 170, outline_alpha=195, width=3)
    draw = ImageDraw.Draw(image)
    draw.text((90, 88), brand_name.upper(), font=_bold(44), fill=GOLD)
    draw.text((90, 150), sport.upper(), font=_font(35), fill=MUTED)
    draw.text((PAGE_W - 250, 90), PNG_RENDERER_VERSION, font=_font(22), fill=MUTED)
    y = 235
    for line in wrap(title, width=18)[:3]:
        y = _center(draw, y, line, _bold(86), fill=INK) + 12
    _panel(image, (110, y + 12, PAGE_W - 110, y + 116), radius=34, alpha=175, outline_alpha=195, width=2)
    draw = ImageDraw.Draw(image)
    _center(draw, y + 38, action[:30], _bold(46), fill=GOLD)
    y += 158
    metric_line = "  •  ".join(_metrics(row)) or "Research / Learning"
    _panel(image, (94, y, PAGE_W - 94, y + 110), radius=30, alpha=150, outline_alpha=155, width=2)
    draw = ImageDraw.Draw(image)
    _wrapped(draw, 126, y + 24, metric_line, _bold(34), width=48, fill=GREEN, max_lines=2, line_gap=8)
    y += 145
    _panel(image, (94, y, PAGE_W - 94, 960), radius=30, alpha=145, outline_alpha=140, width=2)
    draw = ImageDraw.Draw(image)
    draw.text((126, y + 26), "WHY IT MATTERS", font=_bold(38), fill=GOLD)
    _wrapped(draw, 126, y + 86, _reason(row), _font(43), width=34, fill=INK, max_lines=4, line_gap=14)
    _panel(image, (190, 1040, PAGE_W - 190, 1195), radius=38, alpha=165, outline_alpha=190, width=2)
    draw = ImageDraw.Draw(image)
    _center(draw, 1064, "TENDENCY", _bold(48), fill=GOLD)
    _center(draw, 1134, _trend(row)[:28], _bold(56), fill=INK)
    return _png(image)


def render_custom_background_summary_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, top_n: int = 4) -> bytes:
    frame = apply_learning_layer_compat(pd.DataFrame(cards).copy()).head(top_n)
    if frame.empty:
        frame = pd.DataFrame([{"event": "No cards available", "prediction": "Research / Learning"}])
    has_custom = _has_background(background_bytes)
    image = _background(background_bytes)
    if not has_custom:
        _scrim(image, alpha=80)
    brand_name = _brand_value(brand, "brand_name", "ABA Signal Pro")
    title = _brand_value(brand, "report_title", "Daily Sports Analysis")
    workspace = _brand_value(brand, "workspace_id", "report")
    disclaimer = _brand_value(brand, "disclaimer", "Informational content only. Results are not guaranteed.")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    _panel(image, (52, 50, PAGE_W - 52, 262), radius=36, alpha=130 if has_custom else 180, outline_alpha=190, width=3)
    draw = ImageDraw.Draw(image)
    _center(draw, 78, brand_name.upper(), _bold(54), fill=GOLD)
    _center(draw, 150, title, _bold(72), fill=INK)
    _center(draw, 224, f"{today}  •  {workspace}", _font(31), fill=MUTED)
    draw.text((PAGE_W - 320, 226), PNG_RENDERER_VERSION, font=_font(22), fill=MUTED)

    total, official, research, issues = _summary_counts(pd.DataFrame(cards))
    _panel(image, (66, 286, PAGE_W - 66, 372), radius=28, alpha=145, outline_alpha=165, width=2)
    draw = ImageDraw.Draw(image)
    summary = f"Cards {total}   |   Official {official}   |   Research/Watch {research}   |   Data issues {issues}"
    _center(draw, 314, summary, _bold(34), fill=GREEN)

    draw.text((72, 404), "TOP REPORT CARDS", font=_bold(54), fill=GOLD)
    y = 478
    card_h = 182
    for idx, (_, row) in enumerate(frame.iterrows(), start=1):
        item = row.to_dict()
        event = safe_text(item.get("event")) or "Matchup"
        pick = _trend(item)
        action = _action(item)
        metrics = "  •  ".join(_metrics(item)[:4])
        reason = _reason(item)
        _panel(image, (66, y, PAGE_W - 66, y + card_h), radius=30, alpha=150, outline_alpha=190, width=3)
        draw = ImageDraw.Draw(image)
        draw.text((106, y + 20), f"{idx}. {event[:34]}", font=_bold(42), fill=INK)
        draw.text((106, y + 72), pick[:36], font=_bold(37), fill=MUTED)
        draw.text((PAGE_W - 430, y + 24), action[:24], font=_bold(32), fill=GOLD)
        if metrics:
            draw.text((106, y + 116), metrics[:58], font=_bold(27), fill=GREEN)
        _wrapped(draw, 106, y + 148, reason, _font(25), width=70, fill=MUTED, max_lines=1, line_gap=4)
        y += card_h + 22
        if y > 1240:
            break

    _panel(image, (66, 1264, PAGE_W - 66, 1314), radius=22, alpha=130, outline_alpha=130, width=1)
    draw = ImageDraw.Draw(image)
    _center(draw, 1278, disclaimer[:94], _font(24), fill=MUTED)
    return _png(image)


def render_custom_background_deck_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, max_cards: int = 8) -> bytes:
    frame = apply_learning_layer_compat(pd.DataFrame(cards).copy()).head(max_cards)
    if frame.empty:
        frame = pd.DataFrame([{"event": "No cards available", "prediction": "Research / Learning"}])
    pages = []
    for idx, (_, row) in enumerate(frame.iterrows()):
        page_bytes = render_custom_background_card_png(row.to_dict(), brand, background_bytes=background_bytes, index=idx)
        pages.append(Image.open(BytesIO(page_bytes)).convert("RGB"))
    deck = Image.new("RGB", (PAGE_W, PAGE_H * len(pages)), (20, 24, 34))
    for idx, page in enumerate(pages):
        deck.paste(page, (0, idx * PAGE_H))
    return _png(deck)
