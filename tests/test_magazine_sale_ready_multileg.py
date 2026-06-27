from __future__ import annotations

from io import BytesIO

from PIL import Image

import autonomous_betting_agent.magazine_book_export as magazine_book_export
from autonomous_betting_agent.magazine_sale_ready_patch import apply_magazine_sale_ready_patch, sale_ready_chain_items, translate_team_label


def _row(**extra):
    data = {
        "event": "Iraq vs France",
        "sport": "Soccer",
        "prediction": "Game total: Over 2.5",
        "decimal_price": 1.62,
        "model_probability": 0.66,
        "model_market_edge": -0.01,
        "expected_value_per_unit": -0.02,
    }
    data.update(extra)
    return data


def test_sale_ready_chain_items_uses_combo_magazine_items():
    items = sale_ready_chain_items(_row(combo_magazine_items="Line A|Line B|Line C"))
    assert items == ["Line A", "Line B", "Line C"]


def test_sale_ready_chain_items_uses_parlay_magazine_items():
    items = sale_ready_chain_items(_row(parlay_magazine_items="One;Two;Three"))
    assert items == ["One", "Two", "Three"]


def test_sale_ready_chain_items_omits_old_generic_warning_copy():
    joined = " ".join(sale_ready_chain_items(_row()))
    assert "Do not chain" not in joined
    assert "turns positive" not in joined
    assert "before including" not in joined


def test_spanish_no_combo_fallback():
    items = sale_ready_chain_items(_row(report_language="es"))
    assert items[0] == "No se recomienda parlay"


def test_spanish_team_translation_still_available():
    assert translate_team_label("France", "es") == "Francia"
    assert translate_team_label("Iraq", "es") == "Irak"


def test_sale_ready_renderer_removes_visible_version_footer():
    module = apply_magazine_sale_ready_patch(magazine_book_export)
    payload = module.render_full_pick_magazine_page_png(
        _row(combo_magazine_items="No parlay recommended|Not enough compatible selections.|Verified odds are missing."),
        report_name="ABA Signal Pro",
        page_number=1,
        total_pages=1,
        language="en",
    )
    hidden_label = b"v10" + b" no-market"
    assert hidden_label not in payload
    image = Image.open(BytesIO(payload)).convert("RGB")
    right_footer_pixel = image.getpixel((1010, 1562))
    assert not (right_footer_pixel[1] > 120 and right_footer_pixel[0] < 80)
