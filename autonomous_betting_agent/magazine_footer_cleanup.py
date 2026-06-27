from __future__ import annotations

from typing import Any

_PATCH_FLAG = "_ABA_NO_VISIBLE_VERSION_FOOTER_V1"
VISIBLE_VERSION_TEXT = "v10 no-market"


def install(module: Any) -> Any:
    """Remove internal version markers from customer-facing magazine pages.

    The export version still remains in filenames/metadata; this only removes the
    visible green footer tag from rendered pages.
    """
    current_render = getattr(module, "render_full_pick_magazine_page", None)
    if current_render is None or getattr(current_render, _PATCH_FLAG, False):
        return module

    original_render = current_render

    def repaint_customer_footer(image: Any, pick: Any, language: str | None = None) -> Any:
        lang = module._lang(pick, language)
        draw = module.ImageDraw.Draw(image, "RGBA")
        footer_y, footer_b = 1542, 1581
        draw.rectangle((20, footer_y, 1060, footer_b), fill=module.BLACK)
        footer = module._tr(module.SAFETY_FOOTER, lang)
        font = module._fit(footer, module.PAGE_WIDTH - 90, 16, 10, False)
        draw.text(
            (42, footer_y + 10),
            module._ellipsize_to_width(draw, footer, font, module.PAGE_WIDTH - 90),
            font=font,
            fill=module.CREAM,
        )
        return image

    def patched_render(
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
    ) -> Any:
        image = original_render(
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
        return repaint_customer_footer(image, pick, language)

    # Preserve wrapper flags from earlier renderer patches. Without this, a later
    # idempotent sale-ready install can fail to detect that the renderer is already
    # wrapped, re-wrap it after footer cleanup, and make the green internal version
    # marker visible again.
    try:
        patched_render.__dict__.update(getattr(original_render, "__dict__", {}))
    except Exception:
        pass
    setattr(patched_render, _PATCH_FLAG, True)
    module.render_full_pick_magazine_page = patched_render
    return module
