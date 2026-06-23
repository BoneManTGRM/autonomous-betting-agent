from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from textwrap import wrap
from typing import Any, Mapping

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from .report_product_layer import MagazineBrand, safe_text

PNG_HEADER = b"\x89PNG\r\n\x1a\n"

BG = (18, 24, 38)
PANEL = (28, 36, 56)
PANEL_ALT = (36, 48, 72)
TEXT = (245, 248, 255)
MUTED = (178, 190, 210)
ACCENT = (95, 180, 255)
SUCCESS = (101, 220, 160)
WARN = (255, 196, 87)
DANGER = (255, 120, 120)
BORDER = (78, 94, 125)


def _font(size: int = 18) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except Exception:
        return ImageFont.load_default()


def _bold(size: int = 18) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", size)
    except Exception:
        return _font(size)


def safe_filename_part(value: Any, *, fallback: str = "item", limit: int = 70) -> str:
    text = safe_text(value).lower() or fallback
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in text)
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("_") or fallback
    return cleaned[:limit]


def card_image_filename(row: Mapping[str, Any], *, workspace: str = "report", index: int = 0) -> str:
    event = safe_filename_part(row.get("event") or row.get("matchup"), fallback="card")
    workspace_part = safe_filename_part(workspace, fallback="report")
    return f"{workspace_part}_{index + 1:03d}_{event}.png"


def _brand_value(brand: MagazineBrand | Mapping[str, Any] | None, key: str, default: str) -> str:
    if brand is None:
        return default
    if isinstance(brand, Mapping):
        return safe_text(brand.get(key)) or default
    return safe_text(getattr(brand, key, "")) or default


def _png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: Any, *, font: ImageFont.ImageFont, fill: tuple[int, int, int] = TEXT) -> None:
    draw.text(xy, safe_text(value) or "N/A", font=font, fill=fill)


def _wrapped(draw: ImageDraw.ImageDraw, x: int, y: int, value: Any, *, font: ImageFont.ImageFont, fill: tuple[int, int, int] = TEXT, width: int = 80, line_gap: int = 6) -> int:
    lines = wrap(safe_text(value) or "N/A", width=width) or ["N/A"]
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap if hasattr(font, "size") else 22
    return y


def _metric_box(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, label: str, value: Any, *, value_color: tuple[int, int, int] = TEXT) -> None:
    draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=PANEL_ALT, outline=BORDER, width=1)
    draw.text((x + 18, y + 14), label.upper(), font=_bold(14), fill=MUTED)
    draw.text((x + 18, y + 42), safe_text(value) or "N/A", font=_bold(22), fill=value_color)


def _value_color(value: Any) -> tuple[int, int, int]:
    text = safe_text(value).lower()
    if "official" in text or "win" in text or "positive" in text:
        return SUCCESS
    if "blocked" in text or "loss" in text or "negative" in text:
        return DANGER
    if "watch" in text or "research" in text or "thin" in text:
        return WARN
    return TEXT


def render_card_png(row: Mapping[str, Any], brand: MagazineBrand | Mapping[str, Any] | None = None, *, width: int = 1100) -> bytes:
    row = dict(row or {})
    title = safe_text(row.get("event") or row.get("matchup")) or "Matchup"
    sport = safe_text(row.get("public_sport") or row.get("sport")) or "Sport"
    pick = safe_text(row.get("public_pick") or row.get("prediction") or row.get("tendency")) or "N/A"
    action = safe_text(row.get("consumer_action") or row.get("recommended_action")) or "Research / Learning"
    model = safe_text(row.get("model_lean_label") or row.get("confidence_tier")) or "N/A"
    value = safe_text(row.get("price_value_label")) or "N/A"
    official = safe_text(row.get("official_status_label")) or "N/A"
    result = safe_text(row.get("result_status")) or "PENDING"
    learning = safe_text(row.get("learning_status")) or "Needs grading"
    market = safe_text(row.get("market_read")) or "Market read unavailable."
    why = safe_text(row.get("why_it_matters")) or "No extra note available."
    brand_name = _brand_value(brand, "brand_name", "ABA Signal Pro")

    image = Image.new("RGB", (width, 760), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((32, 32, width - 32, 728), radius=28, fill=PANEL, outline=BORDER, width=2)
    draw.text((64, 58), brand_name, font=_bold(24), fill=ACCENT)
    draw.text((64, 96), sport.upper(), font=_bold(18), fill=MUTED)
    draw.text((64, 126), title, font=_bold(34), fill=TEXT)
    draw.rounded_rectangle((64, 178, 64 + min(620, max(240, len(action) * 13)), 224), radius=22, fill=(42, 56, 84), outline=BORDER)
    draw.text((84, 190), action, font=_bold(20), fill=_value_color(action))

    y = 250
    draw.text((64, y), "Pick", font=_bold(16), fill=MUTED)
    y = _wrapped(draw, 64, y + 26, pick, font=_bold(26), fill=TEXT, width=58)
    y += 10

    box_y = y
    box_w = (width - 160) // 4
    _metric_box(draw, 64, box_y, box_w, 92, "Model", model, value_color=_value_color(model))
    _metric_box(draw, 82 + box_w, box_y, box_w, 92, "Value", value, value_color=_value_color(value))
    _metric_box(draw, 100 + box_w * 2, box_y, box_w, 92, "Official", official, value_color=_value_color(official))
    _metric_box(draw, 118 + box_w * 3, box_y, box_w, 92, "Result", result, value_color=_value_color(result))
    y = box_y + 118

    draw.text((64, y), "Learning status", font=_bold(16), fill=MUTED)
    y = _wrapped(draw, 64, y + 26, learning, font=_font(21), fill=TEXT, width=78)
    y += 12
    draw.text((64, y), "Market read", font=_bold(16), fill=MUTED)
    y = _wrapped(draw, 64, y + 26, market, font=_font(21), fill=TEXT, width=88)
    y += 12
    draw.text((64, y), "Why it matters", font=_bold(16), fill=MUTED)
    _wrapped(draw, 64, y + 26, why, font=_font(21), fill=TEXT, width=88)
    return _png_bytes(image)


def render_card_deck_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, max_cards: int = 20, width: int = 1100) -> bytes:
    frame = pd.DataFrame(cards).head(max_cards).copy()
    if frame.empty:
        frame = pd.DataFrame([{"event": "No cards available", "consumer_action": "Research / Learning"}])
    card_h = 560
    header_h = 140
    gap = 24
    height = header_h + len(frame) * (card_h + gap) + 32
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    brand_name = _brand_value(brand, "brand_name", "ABA Signal Pro")
    report_title = _brand_value(brand, "report_title", "Premium Card Deck")
    draw.text((48, 34), brand_name, font=_bold(28), fill=ACCENT)
    draw.text((48, 76), report_title, font=_bold(36), fill=TEXT)
    y = header_h
    for idx, (_, row) in enumerate(frame.iterrows(), start=1):
        item = row.to_dict()
        title = safe_text(item.get("event")) or "Matchup"
        pick = safe_text(item.get("public_pick") or item.get("prediction")) or "N/A"
        action = safe_text(item.get("consumer_action") or item.get("recommended_action")) or "Research / Learning"
        model = safe_text(item.get("model_lean_label") or item.get("confidence_tier")) or "N/A"
        value = safe_text(item.get("price_value_label")) or "N/A"
        result = safe_text(item.get("result_status")) or "PENDING"
        market = safe_text(item.get("market_read")) or "Market read unavailable."
        draw.rounded_rectangle((48, y, width - 48, y + card_h), radius=22, fill=PANEL, outline=BORDER, width=1)
        draw.text((76, y + 28), f"{idx}. {title}", font=_bold(28), fill=TEXT)
        draw.text((76, y + 74), action, font=_bold(20), fill=_value_color(action))
        draw.text((76, y + 118), "Pick", font=_bold(15), fill=MUTED)
        yy = _wrapped(draw, 76, y + 142, pick, font=_bold(23), width=66)
        _metric_box(draw, 76, yy + 14, 230, 86, "Model", model, value_color=_value_color(model))
        _metric_box(draw, 326, yy + 14, 230, 86, "Value", value, value_color=_value_color(value))
        _metric_box(draw, 576, yy + 14, 230, 86, "Result", result, value_color=_value_color(result))
        draw.text((76, yy + 130), "Market read", font=_bold(15), fill=MUTED)
        _wrapped(draw, 76, yy + 154, market, font=_font(20), width=88)
        y += card_h + gap
    return _png_bytes(image)


def _count_bool(cards: pd.DataFrame, column: str) -> int:
    if cards.empty or column not in cards.columns:
        return 0
    return int(cards[column].astype(bool).sum())


def _count_issues(cards: pd.DataFrame) -> int:
    if cards.empty or "data_issue_reason" not in cards.columns:
        return 0
    return int(cards["data_issue_reason"].map(lambda value: bool(safe_text(value))).sum())


def render_magazine_summary_png(cards: pd.DataFrame, brand: MagazineBrand | Mapping[str, Any] | None = None, *, top_n: int = 8, width: int = 1200) -> bytes:
    frame = pd.DataFrame(cards).head(top_n).copy()
    if frame.empty:
        frame = pd.DataFrame([{"event": "No cards available", "consumer_action": "Research / Learning"}])
    official = _count_bool(frame, "official_publish_ready")
    report_ready = _count_bool(frame, "client_report_ready")
    issues = _count_issues(frame)
    research = max(report_ready - official, 0)
    height = 520 + len(frame) * 112
    image = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(image)
    brand_name = _brand_value(brand, "brand_name", "ABA Signal Pro")
    report_title = _brand_value(brand, "report_title", "Sports Analysis Report")
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    draw.rounded_rectangle((42, 36, width - 42, height - 36), radius=30, fill=PANEL, outline=BORDER, width=2)
    draw.text((78, 70), brand_name, font=_bold(30), fill=ACCENT)
    draw.text((78, 116), report_title, font=_bold(42), fill=TEXT)
    draw.text((78, 172), f"Generated: {generated}", font=_font(20), fill=MUTED)
    _metric_box(draw, 78, 224, 250, 96, "Official +EV", official, value_color=SUCCESS)
    _metric_box(draw, 352, 224, 250, 96, "Research", research, value_color=WARN)
    _metric_box(draw, 626, 224, 250, 96, "Data Issues", issues, value_color=DANGER if issues else TEXT)
    _metric_box(draw, 900, 224, 220, 96, "Cards", len(frame), value_color=TEXT)
    draw.text((78, 370), "Top Cards", font=_bold(26), fill=TEXT)
    y = 418
    for idx, (_, row) in enumerate(frame.iterrows(), start=1):
        item = row.to_dict()
        title = safe_text(item.get("event")) or "Matchup"
        pick = safe_text(item.get("public_pick") or item.get("prediction")) or "N/A"
        action = safe_text(item.get("consumer_action") or item.get("recommended_action")) or "Research / Learning"
        result = safe_text(item.get("result_status")) or "PENDING"
        draw.rounded_rectangle((78, y, width - 78, y + 92), radius=18, fill=PANEL_ALT, outline=BORDER)
        draw.text((104, y + 14), f"{idx}. {title}", font=_bold(22), fill=TEXT)
        draw.text((104, y + 48), pick[:96], font=_font(18), fill=MUTED)
        draw.text((width - 390, y + 18), action[:32], font=_bold(18), fill=_value_color(action))
        draw.text((width - 390, y + 50), f"Result: {result}", font=_font(17), fill=_value_color(result))
        y += 112
    return _png_bytes(image)
