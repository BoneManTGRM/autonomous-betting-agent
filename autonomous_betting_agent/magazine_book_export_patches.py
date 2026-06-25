from __future__ import annotations

from typing import Any
import re


def install() -> None:
    """Apply small runtime patches to the magazine renderer.

    This keeps the public renderer API stable while fixing two production layout issues:
    1. Spanish sport labels like Boxing should render as Latin American Spanish.
    2. The top metrics strip needs a wider risk cell for longer risk labels.
    """
    from . import magazine_book_export as m

    if getattr(m, "_aba_magazine_metric_patch_v1", False):
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

    risk_es = {
        "THIN EDGE FAVORITE": "FAVORITO DE VENTAJA DELGADA",
        "THIN EDGE FAVOURITE": "FAVORITO DE VENTAJA DELGADA",
        "VOLUME OK": "VOLUMEN OK",
        "VOLUME_OK": "VOLUMEN OK",
    }

    def patched_tr(v: Any, lang: str) -> str:
        text = original_tr(v, lang)
        if lang != "es" or m._bad(text):
            return text
        raw = str(text)
        for src, dst in sport_es.items():
            raw = re.sub(rf"\b{re.escape(src)}\b", dst, raw, flags=re.I)
        for src, dst in risk_es.items():
            raw = re.sub(rf"\b{re.escape(src)}\b", dst, raw, flags=re.I)
        return raw

    def repaint_risk_market(img, pick: Any, lang: str, sy: int = 456) -> None:
        d = m.ImageDraw.Draw(img, "RGBA")
        risk = patched_tr(
            m._clean(
                m._get(pick, "risk", "risk_level", "risk_label", "profit_guard_status", default=m.NO_VERIFIED),
                True,
            ),
            lang,
        )
        market = patched_tr(
            m._clean(m._get(pick, "market_type", "market", "bet_type", default=m.NO_VERIFIED), True),
            lang,
        )
        # Repaint the far-right metric cells on top of the original strip.
        # Original risk/market widths were 94/94. This gives risk 140px while
        # preserving the overall strip boundary and keeping market readable.
        m._metric(d, 830, sy + 6, 140, "RISK", risk, m.GREEN, lang)
        m._metric(d, 970, sy + 6, 90, "MARKET", market, m.CREAM, lang)

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
        repaint_risk_market(img, pick, m._lang(pick, language))
        return img

    m._tr = patched_tr
    m.render_full_pick_magazine_page = patched_render_full_pick_magazine_page
    m._aba_magazine_metric_patch_v1 = True
