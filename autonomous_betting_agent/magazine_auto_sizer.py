from __future__ import annotations

from typing import Any


def apply_magazine_auto_sizer(module: Any) -> Any:
    """Restore strict text fitting for magazine labels.

    The base renderer sometimes passes a high minimum font size for team names.
    This helper keeps the requested start size but continues shrinking to a safe
    hard floor when the requested minimum is still too wide for the available box.
    """
    if getattr(module, "_STRICT_MAGAZINE_AUTO_SIZER_PATCHED", False):
        return module

    original_font = module._font
    original_image = module.Image
    original_draw_factory = module.ImageDraw.Draw

    def strict_fit(text: str, width: int, start: int, minimum: int = 12, bold: bool = True):
        draw = original_draw_factory(original_image.new("RGB", (10, 10)))
        floor = min(int(minimum), 6)
        for size in range(int(start), floor - 1, -1):
            font = original_font(size, bold)
            if draw.textbbox((0, 0), str(text), font=font)[2] <= width:
                return font
        return original_font(floor, bold)

    module._fit = strict_fit
    module.MAGAZINE_STYLE_VERSION = f"{module.MAGAZINE_STYLE_VERSION}_strict_autosize_v1"
    module._STRICT_MAGAZINE_AUTO_SIZER_PATCHED = True
    return module
