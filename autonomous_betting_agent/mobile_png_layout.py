from __future__ import annotations

from io import BytesIO
from textwrap import wrap
from typing import Any, Mapping

import pandas as pd
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from .report_product_layer import MagazineBrand, safe_text

W = 1080
BG = (35, 42, 62)
WHITE = (255, 255, 255)
SOFT = (226, 233, 245)
GOLD = (255, 214, 79)
GREEN = (125, 245, 180)
PANEL = (8, 12, 22)


def font(size: int):
    for name in ("DejaVuSans.ttf", "DejaVuSerif.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def bold(size: int):
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSerif-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()


def brand_value(brand: MagazineBrand | Mapping[str, Any] | None, key: str, default: str) -> str:
    if isinstance(brand, Mapping):
        return safe_text(brand.get(key)) or default
    if brand is not None:
        return safe_text(getattr(brand, key, "")) or default
    return default


def first(row: Mapping[str, Any], names: tuple[str, ...]) -> str:
    for name in names:
        value = safe_text(row.get(name))
        if value:
            return value
    return ""


def card_text(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    event = safe_text(row.get("event") or row.get("matchup")) or "Matchup"
    pick = first(row, ("public_pick", "prediction", "consumer_action", "recommended_action")) or "Research / Learning"
    status = first(row, ("consumer_action", "recommended_action", "official_status_label", "price_value_label")) or "Research"
    sport = first(row, ("public_sport", "sport", "league")) or "Sports"
    market = first(row, ("market_type", "market")) or "Market"
    price = safe_text(row.get("decimal_price") or row.get("best_price") or row.get("odds_decimal")) or "N/A"
    detail = f"{sport}  |  {market}  |  Price {price}"
    return event, pick, status, detail


def panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    draw.rounded_rectangle(box, radius=34, fill=PANEL, outline=WHITE, width=4)


def write_wrap(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, fnt, width: int, max_lines: int, fill=WHITE, gap: int = 8) -> int:
    h = draw.textbbox((0, 0), "Ag", font=fnt)[3] + gap
    for line in (wrap(safe_text(text), width=width)[:max_lines] or ["N/A"]):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += h
    return y


def render_mobile_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, background_bytes: bytes | None = None, top_n: int = 3) -> bytes:
    frame = pd.DataFrame(cards).head(min(int(top_n or 3), 3))
    if frame.empty:
        frame = pd.DataFrame([{"event": "No rows available", "prediction": "Research / Learning"}])
    card_h = 380
    header_h = 330
    gap = 38
    height = header_h + len(frame) * (card_h + gap) + 82
    try:
        bg = Image.open(BytesIO(background_bytes or b"")).convert("RGB") if background_bytes else Image.new("RGB", (W, height), BG)
        scale = max(W / bg.width, height / bg.height)
        bg = bg.resize((int(bg.width * scale), int(bg.height * scale)))
        bg = bg.crop(((bg.width - W) // 2, max(0, (bg.height - height) // 2), (bg.width + W) // 2, max(0, (bg.height - height) // 2) + height))
    except Exception:
        bg = Image.new("RGB", (W, height), BG)
    img = ImageEnhance.Brightness(bg).enhance(0.58)
    draw = ImageDraw.Draw(img)
    panel(draw, (44, 40, W - 44, 282))
    title = brand_value(brand, "report_title", "Daily Sports Analysis")
    name = brand_value(brand, "brand_name", "ABA Signal Pro")
    draw.text((86, 76), name.upper()[:30], font=bold(56), fill=GOLD)
    draw.text((86, 150), title[:32], font=bold(72), fill=WHITE)
    draw.text((86, 238), "Mobile readable report • 3 cards per image", font=font(34), fill=SOFT)
    y = header_h
    for idx, (_, row) in enumerate(frame.iterrows(), start=1):
        event, pick, status, detail = card_text(row.to_dict())
        panel(draw, (58, y, W - 58, y + card_h))
        write_wrap(draw, 96, y + 26, f"{idx}. {event}", bold(54), 31, 2, WHITE)
        draw.text((96, y + 142), "PICK", font=bold(36), fill=SOFT)
        write_wrap(draw, 210, y + 130, pick, bold(64), 22, 2, GOLD)
        draw.text((96, y + 260), status[:30], font=bold(42), fill=GREEN)
        write_wrap(draw, 96, y + 318, detail, bold(34), 42, 1, SOFT)
        y += card_h + gap
    out = BytesIO()
    img.save(out, format="PNG", optimize=False)
    return out.getvalue()
