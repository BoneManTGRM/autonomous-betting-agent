from pathlib import Path


def test_report_studio_wires_full_magazine_book_exports():
    source = Path("pages/report_studio.py").read_text(encoding="utf-8")

    assert "magazine_book_export" in source
    assert "Download Full Magazine Book" in source
    assert "Save Full Magazine Book PNG" in source
    assert "Save Full Magazine Book PDF" in source
    assert "Save Full Magazine ZIP" in source
    assert "Download Full Magazine Page" in source
    assert "Save Magazine Page PNG" in source
    assert "report_studio_prepare_full_book" in source
    assert "report_studio_prepare_full_page_" in source
    assert "report_studio_image_full_page_" in source
    assert "Download full card deck PNG" not in source
    assert "Download Card Image" not in source
