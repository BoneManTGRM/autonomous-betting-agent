from pathlib import Path


def test_report_studio_wires_full_magazine_book_exports():
    source = Path("pages/report_studio.py").read_text(encoding="utf-8")

    assert "magazine_book_export" in source
    assert "Download Full Magazine Page" in source or "Download Selected Full Magazine Page" in source
    assert "report_studio_image_full_page_" in source
    assert "Download Full Magazine Book PNG" in source
    assert "Download Full Magazine Book PDF" in source
    assert "Download Full Magazine ZIP" in source
    assert "Download full card deck PNG" not in source
    assert "Download Card Image" not in source
    assert "report_studio_image_card_" not in source
    assert "report_studio_image_deck_png" not in source
    assert "Save Magazine Page PNG" not in source
