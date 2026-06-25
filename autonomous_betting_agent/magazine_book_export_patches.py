from __future__ import annotations

from typing import Any, Iterable
import re


def install() -> None:
    """Apply runtime layout patches to the magazine renderer.

    Goals:
    - keep the public renderer API stable;
    - prevent long text from overflowing magazine boxes;
    - render Spanish sport/risk labels in Latin American Spanish;
    - show real uploaded/API row context in team snapshots when available.
    """
    from . import magazine_book_export as m

    if getattr(m, "_aba_magazine_metric_patch_v3", False):
        return

    original_tr = m._tr
    original_render = m.render_full_pick_magazine_page

    sport_es = {
        "BOXING": "BOXEO",
        "BASEBALL": "BÉISBOL",
        "SOCCER": "FÚTBOL",
        "FOOTBALL": "FÚTBOL AMERICANO",
        "BASKETBALL": "BALONCESTO",
        "TENNIS": "TENIS",
        "MMA": "MMA",
        "MLB": "MLB",
        "NCAA BASEBALL": "BÉISBOL NCAA",
    }

    # Full text is too long for the magazine metric strip. These are public-facing
    # compact labels, not grading logic.
    risk_display_es = {
        "THIN EDGE FAVORITE": "VENTAJA DELGADA",
        "THIN EDGE FAVOURITE": "VENTAJA DELGADA",
        "FAVORITO DE VENTAJA DELGADA": "VENTAJA DELGADA",
        "RESEARCH ONLY": "INVESTIGACIÓN",
        "WATCHLIST ONLY": "SEGUIMIENTO",
        "VOLUME OK": "VOLUMEN OK",
        "VOLUME_OK": "VOLUMEN OK",
    }
    risk_display_en = {
        "THIN EDGE FAVORITE": "THIN EDGE",
        "THIN EDGE FAVOURITE": "THIN EDGE",
        "RESEARCH ONLY": "RESEARCH",
        "WATCHLIST ONLY": "WATCHLIST",
        "VOLUME OK": "VOLUME OK",
        "VOLUME_OK": "VOLUME OK",
    }

    def patched_tr(v: Any, lang: str) -> str:
        text = original_tr(v, lang)
        if m._bad(text):
            return text
        raw = str(text)
        if lang == "es":
            for src, dst in sport_es.items():
                raw = re.sub(rf"\b{re.escape(src)}\b", dst, raw, flags=re.I)
            for src, dst in risk_display_es.items():
                raw = re.sub(rf"\b{re.escape(src)}\b", dst, raw, flags=re.I)
        return raw

    def safe_fit(text: str, width: int, start: int, minimum: int = 16, bold: bool = True):
        d = m.ImageDraw.Draw(m.Image.new("RGB", (10, 10)))
        floor = max(4, min(8, int(minimum)))
        for size in range(int(start), floor - 1, -1):
            f = m._font(size, bold)
            if d.textbbox((0, 0), str(text), font=f)[2] <= width:
                return f
        return m._font(floor, bold)

    def safe_txt_auto(
        d,
        x: int,
        y: int,
        text: str,
        width: int,
        height: int,
        start: int,
        minimum: int,
        fill: Any,
        bold: bool = False,
        max_lines: int | None = None,
    ) -> int:
        text = str(text or "")
        floor = max(4, min(8, int(minimum)))
        if max_lines == 1:
            f = safe_fit(text, width, start, floor, bold)
            d.text((x, y), text, font=f, fill=fill)
            return y + m._line_height(f)
        for size in range(int(start), floor - 1, -1):
            f = m._font(size, bold)
            lines = m._wrap(d, text, f, width, max_lines)
            if lines and len(lines) * m._line_height(f) <= height:
                for line in lines:
                    d.text((x, y), line, font=f, fill=fill)
                    y += m._line_height(f)
                return y
        f = m._font(floor, bold)
        bottom = y + height
        for line in m._wrap(d, text, f, width, max_lines):
            if y + m._line_height(f) > bottom:
                break
            d.text((x, y), line, font=f, fill=fill)
            y += m._line_height(f)
        return y

    def safe_bullets_auto(
        d,
        x: int,
        y: int,
        items: list[str],
        width: int,
        height: int,
        color: tuple[int, int, int],
        start: int = 18,
        minimum: int = 11,
        limit: int | None = None,
        lang: str = "en",
    ) -> None:
        data = [patched_tr(item, lang) for item in (items[:limit] if limit is not None else items)]
        floor = max(5, min(8, int(minimum)))
        chosen = None
        chosen_lines: list[list[str]] = []
        for size in range(int(start), floor - 1, -1):
            f = m._font(size)
            blocks = [m._wrap(d, item, f, width - 30, None) for item in data]
            need = sum(max(1, len(block)) * m._line_height(f) + 6 for block in blocks)
            if need <= height:
                chosen = f
                chosen_lines = blocks
                break
        if chosen is None:
            chosen = m._font(floor)
            chosen_lines = [m._wrap(d, item, chosen, width - 30, None) for item in data]
        bottom = y + height
        for block in chosen_lines:
            if y + m._line_height(chosen) > bottom:
                break
            d.ellipse((x, y + 7, x + 12, y + 19), fill=color)
            for line in block:
                if y + m._line_height(chosen) > bottom:
                    break
                d.text((x + 25, y), line, font=chosen, fill=m.TEXT)
                y += m._line_height(chosen)
            y += 6

    def safe_headline_font(text: str, width: int, preferred: int, minimum: int):
        text = str(text or "").upper()
        clean_len = len(text)
        if clean_len <= 5:
            start = preferred
        elif clean_len <= 8:
            start = min(preferred, 106)
        elif clean_len <= 10:
            start = min(preferred, 88)
        elif clean_len <= 14:
            start = min(preferred, 70)
        elif clean_len <= 18:
            start = min(preferred, 58)
        else:
            start = min(preferred, 46)
        return safe_fit(text, width, start, 5, True)

    def _compact_risk(value: Any, lang: str) -> str:
        raw = str(value or "").strip().upper().replace("_", " ")
        mapping = risk_display_es if lang == "es" else risk_display_en
        return mapping.get(raw, raw)

    def _metric_fit(d, x: int, y: int, w: int, label: str, value: str, color: tuple[int, int, int], lang: str) -> None:
        label = patched_tr(label, lang)
        value = str(value or "").upper()
        d.rectangle((x, y, x + w, y + 94), fill=m.BLACK, outline=(230, 224, 204), width=1)
        d.text((x + 7, y + 10), label, font=safe_fit(label, w - 12, 16, 7, True), fill=(232, 230, 220))
        # Wrap compact risk text to two lines and shrink if needed. Never draw into the next cell.
        safe_txt_auto(d, x + 7, y + 43, value, w - 14, 42, 18, 5, color, True, 2)

    def _split_value(value: Any) -> list[str]:
        if m._bad(value):
            return []
        return [p.strip(" -•") for p in str(value).replace("•", "\n").replace(";", "\n").replace("|", "\n").splitlines() if p.strip(" -•")]

    def _first(row: dict[str, Any], keys: Iterable[str]) -> str:
        for key in keys:
            value = row.get(key)
            if not m._bad(value):
                return str(value).strip()
        return ""

    def _team_items(row: dict[str, Any], prefix: str, lang: str) -> list[str]:
        labels = {
            "record": "Récord" if lang == "es" else "Record",
            "last_10": "Últimos 10" if lang == "es" else "Last 10",
            "form": "Forma" if lang == "es" else "Form",
            "rank": "Ranking" if lang == "es" else "Rank",
            "goals": "Goles por partido" if lang == "es" else "Goals per game",
            "runs": "Carreras por partido" if lang == "es" else "Runs per game",
            "injuries": "Lesiones" if lang == "es" else "Injuries",
        }
        specs = [
            (labels["record"], (f"{prefix}_record", f"{prefix}_season_record", f"{prefix}_team_record")),
            (labels["last_10"], (f"{prefix}_last_10", f"{prefix}_recent_record", f"{prefix}_recent_form")),
            (labels["form"], (f"{prefix}_form", f"{prefix}_team_form", f"{prefix}_form_note", f"{prefix}_trend")),
            (labels["rank"], (f"{prefix}_rank", f"{prefix}_standing", f"{prefix}_table_position")),
            (labels["goals"], (f"{prefix}_goals_per_game", f"{prefix}_avg_goals", f"{prefix}_xg")),
            (labels["runs"], (f"{prefix}_runs_per_game", f"{prefix}_rpg")),
            (labels["injuries"], (f"{prefix}_injuries", f"{prefix}_injury_report", f"{prefix}_lineup_status")),
        ]
        out: list[str] = []
        for label, keys in specs:
            value = _first(row, keys)
            if value:
                out.append(f"{label}: {value}")
        for key in (f"{prefix}_snapshot", f"{prefix}_notes", f"{prefix}_team_notes"):
            out.extend(_split_value(row.get(key)))
        return [patched_tr(item, lang) for item in out[:4]]

    def repaint_team_snapshots(img, pick: Any, lang: str, use_team_logo: bool) -> None:
        row = dict(m._row(pick))
        away, home = m._teams(pick)
        away_label, home_label = m._team_label(away, lang), m._team_label(home, lang)
        right_x, right_w = 352, 708
        divider = right_x + right_w // 2
        snap_w = right_w // 2 - 52
        y = 585
        d = m.ImageDraw.Draw(img, "RGBA")
        # Clear only the section body; keep the blue section header.
        d.rectangle((right_x + 3, y + 58, right_x + right_w - 3, y + 362), fill=m.CREAM)
        d.line((divider, 660, divider, 922), fill=m.BLACK + (170,), width=1)
        for x, team, label, color, prefix in (
            (right_x + 24, away, away_label, m.RED, "away"),
            (divider + 24, home, home_label, m.BLUE, "home"),
        ):
            m._badge(img, d, label, x, 675, 50, 50, color, use_team_logo)
            d.text((x + 66, 684), label.upper(), font=safe_fit(label.upper(), snap_w - 70, 25, 7, True), fill=color)
            items = _team_items(row, prefix, lang)
            if not items:
                items = [m.TEAM_DATA_FALLBACK, "Use team form, injuries, and market movement before publishing."]
            safe_bullets_auto(d, x, 751, items, snap_w - 10, 170, color, 18, 6, 4, lang)

    def repaint_risk_market(img, pick: Any, lang: str, sy: int = 456) -> None:
        d = m.ImageDraw.Draw(img, "RGBA")
        risk_raw = m._clean(
            m._get(pick, "risk", "risk_level", "risk_label", "profit_guard_status", default=m.NO_VERIFIED),
            True,
        )
        risk = _compact_risk(patched_tr(risk_raw, lang), lang)
        market = patched_tr(
            m._clean(m._get(pick, "market_type", "market", "bet_type", default=m.NO_VERIFIED), True),
            lang,
        )
        _metric_fit(d, 830, sy + 6, 148, "RISK", risk, m.GREEN, lang)
        m._metric(d, 978, sy + 6, 82, "MARKET", market, m.CREAM, lang)

    def patched_render_full_pick_magazine_page(
        pick: Any,
        background_image: Any = None,
        report_name: str | None = None,
        page_number: int = 1,
        total_pages: int = 1,
        logo_image: Any = None,
        background_mode: str = "hero_right",
        logo_mode: str = "header",
        background_opacity: float = 0.9,
        logo_opacity: float = 1.0,
        use_team_logo: bool = True,
        language: str | None = None,
    ):
        # Patch the global helpers used by the original renderer before calling it.
        m._fit = safe_fit
        m._txt_auto = safe_txt_auto
        m._bullets_auto = safe_bullets_auto
        m._headline_font = safe_headline_font
        img = original_render(
            pick,
            background_image,
            report_name,
            page_number,
            total_pages,
            logo_image,
            background_mode,
            logo_mode,
            background_opacity,
            logo_opacity,
            use_team_logo,
            language,
        )
        lang = m._lang(pick, language)
        repaint_team_snapshots(img, pick, lang, use_team_logo)
        repaint_risk_market(img, pick, lang)
        return img

    m._tr = patched_tr
    m._fit = safe_fit
    m._txt_auto = safe_txt_auto
    m._bullets_auto = safe_bullets_auto
    m._headline_font = safe_headline_font
    m.render_full_pick_magazine_page = patched_render_full_pick_magazine_page
    m._aba_magazine_metric_patch_v1 = True
    m._aba_magazine_metric_patch_v2 = True
    m._aba_magazine_metric_patch_v3 = True
