from __future__ import annotations

from dataclasses import asdict, is_dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import math
import random
import re
from typing import Any, Iterable, Mapping
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

PAGE_WIDTH = 1080
PAGE_HEIGHT = 1620
MAGAZINE_STYLE_VERSION = "premium_v4_reference_readable"

SAFETY_FOOTER = "No guarantees. Bet responsibly. This analysis is for informational purposes only."
ASSET_DIRS = (Path("assets/team_logos"), Path("assets/report_logos"), Path("assets/licensed_logos"))

RED = (190, 30, 28)
BLUE = (19, 66, 108)
BLACK = (13, 14, 16)
PAPER = (244, 235, 211)
CREAM = (255, 248, 230)
GREEN = (61, 205, 84)
YELLOW = (235, 198, 74)
DANGER = (225, 67, 62)
TEXT = (14, 17, 21)
NO_VERIFIED = "Data unavailable"
NOT_PROVIDED = "Not provided"
TEAM_DATA_FALLBACK = "Data not available from uploaded row"
PLAYER_DATA_FALLBACK = "Player data not available in uploaded row"


def _row(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return data if isinstance(data, Mapping) else {}
    return getattr(value, "__dict__", {}) or {}


def _bad(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip().lower() in {"", "nan", "none", "null", "n/a", "na", "nat", "--"}


def _text(row: Any, *keys: str, default: str = "") -> str:
    data = _row(row)
    for key in keys:
        value = data.get(key)
        if not _bad(value):
            return str(value).strip()
    return default


def _num(row: Any, *keys: str) -> float | None:
    for key in keys:
        value = _row(row).get(key)
        if _bad(value):
            continue
        try:
            return float(str(value).replace("%", "").replace(",", ""))
        except Exception:
            pass
    return None


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = (
        ("DejaVuSansCondensed-Bold.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf")
        if bold
        else ("DejaVuSansCondensed.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf")
    )
    for root in (
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/truetype/liberation2",
        "/usr/share/fonts/truetype/liberation",
    ):
        for name in names:
            try:
                return ImageFont.truetype(str(Path(root) / name), size)
            except Exception:
                pass
    return ImageFont.load_default()


def _fit(text: str, width: int, start: int, minimum: int = 18, bold: bool = True) -> ImageFont.ImageFont:
    drawer = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for size in range(start, minimum - 1, -2):
        font = _font(size, bold)
        if drawer.textbbox((0, 0), str(text or ""), font=font)[2] <= width:
            return font
    return _font(minimum, bold)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").lower()).strip("_")


def _clean_words(value: Any, upper: bool = False) -> str:
    if _bad(value):
        return NO_VERIFIED
    text = str(value).strip().replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    return text.upper() if upper else text


def _fmt(value: Any, kind: str = "text") -> str:
    if _bad(value):
        return NO_VERIFIED
    raw = str(value).strip()
    try:
        number = float(raw.replace("%", "").replace(",", ""))
        if kind == "odds":
            if abs(number) >= 100 and number.is_integer():
                return f"{int(number):+d}" if number > 0 else str(int(number))
            return f"{number:.2f}".rstrip("0").rstrip(".")
        if kind == "ev":
            return f"{number:+.3f}" if abs(number) < 1 else f"{number:+.2f}"
        if kind == "unit":
            return f"{number:.1f}" if abs(number) < 10 else f"{number:.0f}"
        return f"{number:.2f}".rstrip("0").rstrip(".")
    except Exception:
        return _clean_words(raw, upper=kind in {"risk", "market"})


def _pct(value: float | None) -> str:
    if value is None:
        return NO_VERIFIED
    value = value / 100 if abs(value) > 1 else value
    return f"{value:.0%}"


def _edge(value: float | None) -> str:
    if value is None:
        return NO_VERIFIED
    value = value / 100 if abs(value) > 1 else value
    return f"{value:+.1%}"


def _risk_color(value: str) -> tuple[int, int, int]:
    low = str(value).lower()
    if "high" in low or "red" in low:
        return DANGER
    if "medium" in low or "moderate" in low or "yellow" in low:
        return YELLOW
    if "unavailable" in low:
        return CREAM
    return GREEN


def _split(value: Any) -> list[str]:
    if _bad(value):
        return []
    text = str(value).replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [part.strip(" -•") for part in text.splitlines() if part.strip(" -•")]


def _wrap(draw: ImageDraw.ImageDraw, text: Any, font: ImageFont.ImageFont, width: int, max_lines: int = 1) -> list[str]:
    words = str(text or "").replace("\n", " ").split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), trial, font=font)[2] <= width:
            current = trial
            continue
        if current:
            lines.append(current)
        current = word
        if len(lines) >= max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and len(" ".join(lines).split()) < len(words):
        lines[-1] = lines[-1].rstrip(".,;:") + "..."
    return lines


def _txt(draw: ImageDraw.ImageDraw, x: int, y: int, text: Any, font: ImageFont.ImageFont, fill: tuple[int, int, int] | str, width: int, max_lines: int = 1, gap: int = 5) -> int:
    for line in _wrap(draw, text, font, width, max_lines):
        draw.text((x, y), line, font=font, fill=fill)
        y += getattr(font, "size", 18) + gap
    return y


def find_local_team_logo(team_name: str) -> Path | None:
    stem = _slug(team_name)
    if not stem:
        return None
    variants = {stem, stem.replace("_", "-"), stem.replace("_", "")}
    for folder in ASSET_DIRS:
        for variant in variants:
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                path = folder / f"{variant}{ext}"
                if path.exists():
                    return path
    return None


def _load_image(value: Any) -> Image.Image | None:
    try:
        if isinstance(value, (bytes, bytearray)):
            return Image.open(BytesIO(value)).convert("RGBA")
        if isinstance(value, Image.Image):
            return value.convert("RGBA")
        if isinstance(value, (str, Path)) and Path(value).exists():
            return Image.open(value).convert("RGBA")
    except Exception:
        return None
    return None


def _resample() -> int:
    return getattr(getattr(Image, "Resampling", Image), "LANCZOS")


def _cover(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    width, height = size
    scale = max(width / max(1, image.width), height / max(1, image.height))
    resized = image.resize((max(1, int(image.width * scale)), max(1, int(image.height * scale))), _resample())
    x = max(0, (resized.width - width) // 2)
    y = max(0, (resized.height - height) // 2)
    return resized.crop((x, y, x + width, y + height))


def _contain(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    copy = image.copy()
    copy.thumbnail(size, _resample())
    return copy


def _logo_image(path: Path | None, size: tuple[int, int]) -> Image.Image | None:
    if not path:
        return None
    try:
        image = Image.open(path).convert("RGBA")
        image.thumbnail(size, _resample())
        return image
    except Exception:
        return None


def _initials(value: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", str(value or "").upper())
    return "".join(part[0] for part in parts[:3]) or "TM"


def _badge(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, text: str, color: tuple[int, int, int]) -> None:
    draw.rounded_rectangle((x, y, x + w, y + h), radius=8, fill=color, outline=CREAM, width=2)
    label = _initials(text)[:3]
    font = _fit(label, w - 8, max(20, h // 2), 13, True)
    box = draw.textbbox((0, 0), label, font=font)
    draw.text((x + (w - (box[2] - box[0])) / 2, y + (h - (box[3] - box[1])) / 2 - 2), label, font=font, fill="white")


def _logo_or_badge(image: Image.Image, draw: ImageDraw.ImageDraw, text: str, x: int, y: int, w: int, h: int, color: tuple[int, int, int], use_team_logo: bool = True) -> None:
    logo = _logo_image(find_local_team_logo(text), (w, h)) if use_team_logo else None
    if logo:
        image.alpha_composite(logo, (x + (w - logo.width) // 2, y + (h - logo.height) // 2))
    else:
        _badge(draw, x, y, w, h, text, color)


def _game(row: Any) -> str:
    return _text(row, "event", "game", "event_name", "matchup", default="Unknown Matchup")


def _teams(row: Any) -> tuple[str, str]:
    away = _text(row, "away_team", "team_a", "team1")
    home = _text(row, "home_team", "team_b", "team2")
    if away and home:
        return away, home
    game = _game(row)
    for separator in (" at ", " vs ", " VS ", " v ", " @ "):
        if separator in game:
            left, right = game.split(separator, 1)
            return left.strip(), right.strip()
    return _text(row, "team", default="Team A"), _text(row, "opponent", default="Team B")


def _seed(row: Any) -> int:
    data = _row(row)
    raw = "|".join(str(data.get(key, "")) for key in ("sport", "home_team", "away_team", "prediction", "event_start_utc", "event"))
    return int(sha256(raw.encode()).hexdigest()[:16], 16)


def _pick(row: Any) -> str:
    return _text(row, "prediction", "exact_bet", "pick", "selection", "recommended_action", "consumer_action", default=NOT_PROVIDED)


def _risk(row: Any) -> str:
    return _clean_words(_text(row, "risk", "risk_level", "risk_label", "profit_guard_status", "weather_flag", "injury_risk_score", default=NO_VERIFIED), upper=True)


def _why(row: Any) -> list[str]:
    bullets: list[str] = []
    for key in ("why_bullets", "why_pick", "analysis_summary", "reason", "explanation"):
        bullets += _split(_row(row).get(key))
    if bullets:
        return bullets[:4]
    items: list[str] = []
    probability = _pct(_num(row, "learned_model_probability", "model_probability_clean", "model_probability", "final_probability"))
    market = _pct(_num(row, "market_probability", "market_implied_probability"))
    edge = _edge(_num(row, "model_market_edge", "edge"))
    ev = _fmt(_text(row, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev"), "ev")
    if probability != NO_VERIFIED:
        items.append(f"Model projects {probability} probability for {_pick(row)}.")
    if market != NO_VERIFIED:
        items.append(f"Market-implied probability checks at {market}.")
    if edge != NO_VERIFIED:
        items.append(f"Measured edge: {edge}.")
    if ev != NO_VERIFIED:
        items.append(f"Expected value: {ev}.")
    return (items or ["Use only while the line remains playable."])[:4]


def _items(row: Any, keys: Iterable[str], fallback: str, limit: int) -> list[str]:
    output: list[str] = []
    data = _row(row)
    for key in keys:
        output += _split(data.get(key))
    return (output or [fallback])[:limit]


def _pairs(row: Any) -> list[tuple[str, str]]:
    pairs = [
        ("ODDS SOURCE", _text(row, "odds_source", "data_source", default=NO_VERIFIED)),
        ("SPORTSBOOK", _text(row, "bookmaker", "sportsbook", default=NO_VERIFIED)),
        ("LINE MOVE", _text(row, "line_movement", "price_movement", "market_move", default=NO_VERIFIED)),
        ("PUBLIC %", _pct(_num(row, "public_percent", "public_bet_percent", "public_pct"))),
        ("PRO %", _pct(_num(row, "pro_percent", "sharp_percent", "smart_money_percent"))),
    ]
    return [(label, _clean_words(value, upper=False)) for label, value in pairs if value != NO_VERIFIED][:5]


def _stats(row: Any, prefix: str) -> list[tuple[str, str]]:
    fields = (
        ("RECORD", ("record", "season_record")),
        ("LAST 10", ("last_10", "last_ten", "recent_form")),
        ("TEAM AVG", ("team_avg", "batting_average", "fg_pct")),
        ("SCORING", ("runs_per_game", "points_per_game", "goals_per_game")),
    )
    data = _row(row)
    output: list[tuple[str, str]] = []
    for label, keys in fields:
        for key in keys:
            value = data.get(f"{prefix}_{key}")
            if not _bad(value):
                output.append((label, _fmt(value)))
                break
    return output[:3]


def _paper(seed: int) -> Image.Image:
    rng = random.Random(seed)
    image = Image.new("RGBA", (PAGE_WIDTH, PAGE_HEIGHT), PAPER + (255,))
    draw = ImageDraw.Draw(image, "RGBA")
    for _ in range(260):
        x, y = rng.randint(0, PAGE_WIDTH - 1), rng.randint(0, PAGE_HEIGHT - 1)
        q = rng.randint(35, 130)
        draw.rectangle((x, y, x + rng.randint(1, 2), y + rng.randint(1, 2)), fill=(q, q, q, rng.randint(4, 16)))
    for _ in range(30):
        x, y = rng.randint(0, PAGE_WIDTH), rng.randint(0, PAGE_HEIGHT)
        draw.line((x, y, x + rng.randint(-60, 60), y + rng.randint(-12, 12)), fill=(80, 52, 34, rng.randint(5, 14)), width=1)
    draw.rectangle((10, 10, PAGE_WIDTH - 10, PAGE_HEIGHT - 10), outline=RED + (220,), width=4)
    draw.rectangle((16, 16, PAGE_WIDTH - 16, PAGE_HEIGHT - 16), outline=BLACK + (180,), width=2)
    return image


def _draw_hero_art(base: Image.Image, bg: Any, mode: str, opacity: float, away: str, home: str) -> None:
    draw = ImageDraw.Draw(base, "RGBA")
    mode = str(mode or "hero_right").lower()
    loaded = _load_image(bg)
    if mode == "none":
        loaded = None
    if loaded is not None and mode == "full_page":
        layer = _cover(loaded, (PAGE_WIDTH, PAGE_HEIGHT)).filter(ImageFilter.GaussianBlur(1.0))
        layer = ImageEnhance.Color(layer).enhance(0.42)
        layer.putalpha(int(255 * min(max(opacity, 0.08), 0.12)))
        base.alpha_composite(layer, (0, 0))
        overlay = Image.new("RGBA", (PAGE_WIDTH, PAGE_HEIGHT), PAPER + (150,))
        base.alpha_composite(overlay, (0, 0))
        return
    if loaded is not None and mode == "watermark":
        mark = _contain(loaded, (560, 420))
        mark = ImageEnhance.Color(mark).enhance(0.55)
        mark.putalpha(int(255 * min(max(opacity, 0.10), 0.15)))
        base.alpha_composite(mark, (PAGE_WIDTH - mark.width - 34, 120))
        return
    if loaded is not None:
        slot = _cover(loaded, (430, 340))
        slot = ImageEnhance.Color(slot).enhance(0.75)
        slot = ImageEnhance.Contrast(slot).enhance(1.05)
        alpha = int(255 * min(max(opacity, 0.55), 0.75))
        mask = Image.new("L", (430, 340), alpha)
        rounded = Image.new("L", (430, 340), 0)
        ImageDraw.Draw(rounded).rounded_rectangle((0, 0, 430, 340), radius=24, fill=255)
        mask = Image.composite(mask, Image.new("L", (430, 340), 0), rounded)
        slot.putalpha(mask)
        base.alpha_composite(slot, (620, 112))
        draw = ImageDraw.Draw(base, "RGBA")
        draw.rounded_rectangle((620, 112, 1050, 452), radius=24, outline=BLACK + (180,), width=2)
        return
    draw.ellipse((650, 118, 1110, 430), fill=BLUE + (74,))
    for i in range(12):
        draw.line((620 + i * 25, 420, 850 + i * 25, 120), fill=RED + (70,), width=9)


def _user_logo(image: Image.Image, logo: Any, mode: str, opacity: float) -> None:
    if str(mode or "header").lower() == "none":
        return
    loaded = _load_image(logo)
    if loaded is None:
        return
    max_size = (190, 54) if mode == "header" else (440, 260)
    loaded.thumbnail(max_size, _resample())
    alpha = min(max(opacity, 0.08), 0.18) if mode == "watermark" else max(0, min(1, opacity))
    loaded.putalpha(int(255 * alpha))
    image.alpha_composite(loaded, (PAGE_WIDTH - loaded.width - 42, 170) if mode == "watermark" else (638, 20))


def _header(draw: ImageDraw.ImageDraw, image: Image.Image, page: int, total: int, logo: Any, logo_mode: str, logo_opacity: float) -> None:
    draw.rectangle((18, 18, PAGE_WIDTH - 18, 82), fill=BLACK)
    draw.rectangle((30, 26, 292, 74), fill=RED)
    draw.text((43, 34), "ABA SIGNAL PRO", font=_fit("ABA SIGNAL PRO", 232, 31, 24, True), fill="white")
    draw.text((328, 35), "DAILY SPORTS ANALYSIS", font=_font(31, True), fill="white")
    _user_logo(image, logo, logo_mode, logo_opacity)
    draw.rounded_rectangle((854, 26, PAGE_WIDTH - 38, 74), radius=5, fill=CREAM, outline=BLACK)
    draw.text((890, 36), f"PAGE {page} OF {total}", font=_font(26, True), fill=BLACK)


def _section(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, title: str, color: tuple[int, int, int], icon: str = "★") -> None:
    draw.rounded_rectangle((x, y, x + w, y + h), radius=14, fill=CREAM + (252,), outline=BLACK + (235,), width=3)
    draw.rounded_rectangle((x, y, x + w, y + 54), radius=10, fill=color)
    draw.text((x + 18, y + 12), icon, font=_font(24, True), fill=CREAM)
    header_font = _fit(title.upper(), w - 66, 27, 18, True)
    draw.text((x + 54, y + 11), title.upper(), font=header_font, fill=CREAM)


def _bullets(draw: ImageDraw.ImageDraw, x: int, y: int, items: list[str], width: int, color: tuple[int, int, int], limit: int, font_size: int = 20, lines: int = 2) -> None:
    font = _font(font_size)
    for item in items[:limit]:
        draw.ellipse((x, y + 8, x + 12, y + 20), fill=color)
        y = _txt(draw, x + 25, y, item, font, TEXT, width - 30, lines, 4)
        y += 8


def _metric(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, label: str, value: str, color: tuple[int, int, int]) -> None:
    draw.rectangle((x, y, x + w, y + 94), fill=BLACK, outline=(230, 224, 204), width=1)
    draw.text((x + 10, y + 10), label.upper(), font=_font(17, True), fill=(232, 230, 220))
    clean_value = _clean_words(value, upper=True)
    _txt(draw, x + 10, y + 43, clean_value, _fit(clean_value, w - 18, 31, 17, True), color, w - 18, 1)


def _stat_line(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, value: str, width: int) -> int:
    draw.text((x, y), label.upper(), font=_font(18, True), fill=BLACK)
    font = _font(23, True)
    box = draw.textbbox((0, 0), value, font=font)
    draw.text((x + width - (box[2] - box[0]), y - 2), value, font=font, fill=BLACK)
    return y + 31


def _team_snapshot(image: Image.Image, draw: ImageDraw.ImageDraw, x: int, y: int, width: int, team: str, prefix: str, color: tuple[int, int, int], row: Any, use_team_logo: bool) -> None:
    _logo_or_badge(image, draw, team, x, y, 48, 48, color, use_team_logo)
    draw.text((x + 62, y + 8), team.upper(), font=_fit(team.upper(), width - 66, 24, 15, True), fill=color)
    stats = _stats(row, prefix)
    cursor = y + 62
    if stats:
        for label, value in stats[:3]:
            cursor = _stat_line(draw, x, cursor, label, value, width - 6)
        notes = _items(row, (f"{prefix}_notes", f"{prefix}_snapshot", f"{prefix}_context", f"{prefix}_team_snapshot"), TEAM_DATA_FALLBACK, 1)
        draw.text((x, cursor + 8), "NOTES", font=_font(18, True), fill=RED)
        _bullets(draw, x, cursor + 38, notes, width - 10, BLUE, 1, 17, 2)
    else:
        _bullets(draw, x, cursor + 12, [TEAM_DATA_FALLBACK], width - 10, BLUE, 1, 18, 2)


def _player_notes(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, team: str, prefix: str, color: tuple[int, int, int], row: Any) -> None:
    draw.text((x, y), team.upper(), font=_fit(team.upper(), width, 20, 14, True), fill=color)
    items = _items(row, (f"{prefix}_injuries", f"{prefix}_injury_report", f"{prefix}_lineup_status", f"{prefix}_player_notes", "injury_report", "injuries", "lineup_status", "key_players"), PLAYER_DATA_FALLBACK, 2)
    _bullets(draw, x, y + 34, items, width, color, 2, 17, 2)


def _recommend(row: Any) -> tuple[str, str]:
    return (
        _text(row, "final_decision", "agent_decision", "recommendation", "consumer_action", "recommended_action", default="PLAY STANDARD"),
        _text(row, "final_explanation", "action_reason", "recommendation_reason", "decision_reasons", default="Use only if the line remains playable and key news does not change."),
    )


def sanitize_image_filename(value: str, suffix: str = "", extension: str = "png") -> str:
    clean = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "magazine").lower()).strip("_") or "magazine"
    suff = re.sub(r"[^A-Za-z0-9]+", "_", str(suffix or "").lower()).strip("_")
    ext = (extension or "png").lstrip(".")
    return f"{clean + '_' + suff if suff else clean}.{ext}"


def pick_full_page_filename(pick: Any, index: int, extension: str = "png") -> str:
    return sanitize_image_filename(f"pick_{index + 1:02d}_{_game(pick)}", "full_page", extension)


def render_full_pick_magazine_page(
    pick: Any,
    background_image: Any = None,
    report_name: str | None = None,
    page_number: int = 1,
    total_pages: int = 1,
    logo_image: Any = None,
    background_mode: str = "hero_right",
    logo_mode: str = "header",
    background_opacity: float = 0.65,
    logo_opacity: float = 1.0,
    use_team_logo: bool = True,
) -> Image.Image:
    away, home = _teams(pick)
    sport = _text(pick, "sport", "league", default="Sport N/A")
    source = _text(pick, "odds_source", "data_source", "bookmaker", "sportsbook", default="Agent row")
    report = (report_name or "Full Pick Magazine").upper()
    date = _text(pick, "report_date", "event_date", "event_start_utc", default=NOT_PROVIDED)

    image = _paper(_seed(pick))
    _draw_hero_art(image, background_image, background_mode, background_opacity, away, home)
    draw = ImageDraw.Draw(image, "RGBA")
    _header(draw, image, page_number, total_pages, logo_image, logo_mode, logo_opacity)

    _txt(draw, 38, 96, f"REPORT: {report}", _font(19, True), BLACK, 285, 1)
    draw.text((336, 96), "★", font=_font(19, True), fill=BLACK)
    _txt(draw, 366, 96, f"SOURCE: {source.upper()}", _font(19, True), BLACK, 205, 1)
    draw.text((586, 96), "|", font=_font(19, True), fill=BLACK)
    _txt(draw, 618, 96, f"DATE: {date.upper()}", _font(19, True), BLACK, 240, 1)

    draw.rounded_rectangle((908, 92, 1042, 172), radius=8, fill=BLACK, outline=CREAM, width=3)
    draw.text((932, 108), sport.upper()[:12], font=_font(23, True), fill=CREAM)
    _logo_or_badge(image, draw, sport, 950, 134, 64, 34, BLUE, use_team_logo)

    draw.text((38, 132), away.upper(), font=_fit(away.upper(), 600, 98, 56, True), fill=RED)
    draw.text((42, 252), "VS", font=_font(44, True), fill=BLACK)
    draw.line((42, 308, 102, 308), fill=BLACK, width=4)
    draw.text((118, 242), home.upper(), font=_fit(home.upper(), 560, 78, 46, True), fill=BLUE)

    season = _text(pick, "season_label", "event_stage", "competition_round", default=(f"{sport} REGULAR SEASON" if sport != "Sport N/A" else "MATCHUP ANALYSIS"))
    draw.rectangle((38, 334, 510, 380), fill=BLACK)
    _txt(draw, 56, 342, season.upper(), _fit(season.upper(), 440, 26, 18, True), CREAM, 440, 1)

    context: list[str] = []
    for key in ("preview_summary", "game_summary", "sports_context_summary", "short_reason", "decision_reasons"):
        context += _split(_row(pick).get(key))
    cursor = 398
    for line in (context or ["Context unavailable.", "Confirm price and lineup news before entry."])[:2]:
        cursor = _txt(draw, 42, cursor, line, _font(21), TEXT, 565, 1, 4)

    strip_y = 470
    draw.rounded_rectangle((20, strip_y, PAGE_WIDTH - 20, strip_y + 104), radius=12, fill=BLACK, outline=CREAM, width=3)
    draw.text((50, strip_y + 16), "TENDENCIA", font=_font(26, True), fill=RED)
    pick_text = _clean_words(_pick(pick), upper=True)
    draw.text((50, strip_y + 52), pick_text, font=_fit(pick_text, 220, 33, 20, True), fill=CREAM)
    _logo_or_badge(image, draw, home, 268, strip_y + 27, 58, 50, BLUE, use_team_logo)

    odds = _fmt(_text(pick, "american_odds", "odds_american", "decimal_price", "odds_at_pick", "best_price", "odds"), "odds")
    conf = _pct(_num(pick, "learned_model_probability", "model_probability_clean", "model_probability", "final_probability"))
    edge = _edge(_num(pick, "model_market_edge", "edge"))
    ev = _fmt(_text(pick, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev"), "ev")
    units = _fmt(_text(pick, "recommended_stake_units", "suggested_stake_units", "units", default="1.0"), "unit")
    risk = _risk(pick)
    market = _clean_words(_text(pick, "market_type", "market", "bet_type", default=NO_VERIFIED), upper=True)
    x = 344
    for (label, value, color), width in zip(
        [
            ("ODDS", odds, CREAM),
            ("CONFIDENCE", conf, GREEN),
            ("EDGE", edge, GREEN if not edge.startswith("-") else DANGER),
            ("EV", ev, GREEN if not ev.startswith("-") else DANGER),
            ("UNITS", units, CREAM),
            ("RISK", risk, _risk_color(risk)),
            ("MARKET", market, CREAM),
        ],
        [92, 138, 106, 112, 96, 104, 104],
    ):
        _metric(draw, x, strip_y + 5, width, label, value, color)
        x += width

    _section(draw, 20, 600, 350, 282, "WHY WE PICKED IT", RED, "★")
    _bullets(draw, 44, 668, _why(pick), 306, RED, 4, 20, 2)

    _section(draw, 20, 902, 350, 218, "PRO BETTOR EVIDENCE", BLUE, "●")
    row_y = 970
    for label, value in _pairs(pick):
        draw.text((44, row_y), f"{label}:", font=_font(18, True), fill=BLACK)
        _txt(draw, 184, row_y, value, _font(18, True), BLACK, 160, 1, 2)
        row_y += 31
    draw.rectangle((28, 1076, 362, 1112), fill=BLUE)
    _txt(draw, 42, 1084, _text(pick, "evidence_summary", default="Market and model evidence support this read."), _font(17, True), CREAM, 304, 1)

    _section(draw, 386, 600, 674, 336, "TEAM SNAPSHOTS", BLUE, "♟")
    draw.line((724, 670, 724, 914), fill=BLACK + (170,), width=1)
    _team_snapshot(image, draw, 410, 680, 292, away, "away", RED, pick, use_team_logo)
    _team_snapshot(image, draw, 746, 680, 292, home, "home", BLUE, pick, use_team_logo)

    _section(draw, 386, 956, 674, 164, "PLAYER / INJURY NOTES", BLUE, "♟")
    draw.line((724, 1018, 724, 1100), fill=BLACK + (160,), width=1)
    _player_notes(draw, 410, 1026, 292, away, "away", RED, pick)
    _player_notes(draw, 746, 1026, 292, home, "home", BLUE, pick)

    _section(draw, 20, 1142, 340, 204, "RISK DESK", RED, "♢")
    _bullets(draw, 44, 1212, _items(pick, ("why_lose", "risk_reason", "hidden_risk", "risk_notes"), f"Risk status: {risk}", 3), 292, RED, 3, 18, 2)

    _section(draw, 374, 1142, 332, 204, "MATCHUP NOTES", BLUE, "●")
    _bullets(draw, 398, 1212, _items(pick, ("matchup_note", "matchup_notes", "head_to_head", "h2h", "venue_note", "weather_location", "sports_context_summary"), "Matchup context unavailable from current row/API feed.", 3), 284, BLUE, 3, 18, 2)

    _section(draw, 720, 1142, 340, 204, "CHAIN BETTING NOTES", BLUE, "↗")
    _bullets(draw, 744, 1212, _items(pick, ("chain_notes", "main_read", "add_on_legs", "parlay_notes"), "Better as an individual straight analysis unless another verified edge exists.", 2), 292, BLUE, 2, 18, 2)

    action, explanation = _recommend(pick)
    final_y = 1380
    draw.rounded_rectangle((20, final_y, PAGE_WIDTH - 20, 1562), radius=14, fill=BLACK, outline=RED, width=3)
    draw.rectangle((20, final_y, 250, 1562), fill=RED)
    draw.text((40, final_y + 36), "FINAL", font=_font(34, True), fill=CREAM)
    draw.text((40, final_y + 84), "RECOMMENDATION", font=_font(30, True), fill=CREAM)
    action_text = _clean_words(action, upper=True)
    draw.text((284, final_y + 30), action_text, font=_fit(action_text, 320, 56, 34, True), fill=GREEN)
    _txt(draw, 284, final_y + 98, pick_text, _fit(pick_text, 340, 36, 24, True), CREAM, 340, 1)
    _txt(draw, 660, final_y + 44, explanation, _font(22), CREAM, 350, 3)

    draw.rectangle((20, 1568, PAGE_WIDTH - 20, 1606), fill=BLACK)
    footer_box = draw.textbbox((0, 0), SAFETY_FOOTER, font=_font(17))
    draw.text(((PAGE_WIDTH - (footer_box[2] - footer_box[0])) / 2, 1578), SAFETY_FOOTER, font=_font(17), fill=CREAM)
    return image.convert("RGB")


def _png(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()


def render_full_pick_magazine_page_png(
    pick: Any,
    background_image: Any = None,
    report_name: str | None = None,
    page_number: int = 1,
    total_pages: int = 1,
    logo_image: Any = None,
    background_mode: str = "hero_right",
    logo_mode: str = "header",
    background_opacity: float = 0.65,
    logo_opacity: float = 1.0,
    use_team_logo: bool = True,
) -> bytes:
    return _png(render_full_pick_magazine_page(pick, background_image, report_name, page_number, total_pages, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo))


def render_full_magazine_book_pages(
    picks: Iterable[Any],
    background_image: Any = None,
    report_name: str | None = None,
    logo_image: Any = None,
    background_mode: str = "hero_right",
    logo_mode: str = "header",
    background_opacity: float = 0.65,
    logo_opacity: float = 1.0,
    use_team_logo: bool = True,
) -> list[Image.Image]:
    rows = list(picks) or [{"event": "No Picks", "prediction": "NO PICK"}]
    return [render_full_pick_magazine_page(row, background_image, report_name, index + 1, len(rows), logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo) for index, row in enumerate(rows)]


def render_full_magazine_book_png(
    picks: Iterable[Any],
    background_image: Any = None,
    report_name: str | None = None,
    logo_image: Any = None,
    background_mode: str = "hero_right",
    logo_mode: str = "header",
    background_opacity: float = 0.65,
    logo_opacity: float = 1.0,
    use_team_logo: bool = True,
) -> bytes:
    pages = render_full_magazine_book_pages(picks, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo)
    book = Image.new("RGB", (PAGE_WIDTH, PAGE_HEIGHT * len(pages)), PAPER)
    for index, page in enumerate(pages):
        book.paste(page, (0, PAGE_HEIGHT * index))
    return _png(book)


def render_full_magazine_book_pdf(
    picks: Iterable[Any],
    background_image: Any = None,
    report_name: str | None = None,
    logo_image: Any = None,
    background_mode: str = "hero_right",
    logo_mode: str = "header",
    background_opacity: float = 0.65,
    logo_opacity: float = 1.0,
    use_team_logo: bool = True,
) -> bytes:
    pages = [page.convert("RGB") for page in render_full_magazine_book_pages(picks, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo)]
    output = BytesIO()
    pages[0].save(output, format="PDF", save_all=True, append_images=pages[1:], resolution=100.0)
    return output.getvalue()


def render_full_magazine_zip(
    picks: Iterable[Any],
    background_image: Any = None,
    report_name: str | None = None,
    logo_image: Any = None,
    background_mode: str = "hero_right",
    logo_mode: str = "header",
    background_opacity: float = 0.65,
    logo_opacity: float = 1.0,
    use_team_logo: bool = True,
) -> bytes:
    rows = list(picks)
    pages = render_full_magazine_book_pages(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo)
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("full_magazine_book.png", render_full_magazine_book_png(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo))
        archive.writestr("full_magazine_book.pdf", render_full_magazine_book_pdf(rows, background_image, report_name, logo_image, background_mode, logo_mode, background_opacity, logo_opacity, use_team_logo))
        for index, page in enumerate(pages):
            archive.writestr(pick_full_page_filename(rows[index] if index < len(rows) else {"event": "No Picks"}, index), _png(page))
    return output.getvalue()
