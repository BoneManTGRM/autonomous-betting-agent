from pathlib import Path


def test_report_studio_wires_full_magazine_book_exports():
    source = Path("pages/report_studio.py").read_text(encoding="utf-8")

    assert "magazine_book_export" in source
    assert "Download Full Magazine Book PNG" in source
    assert "Download Full Magazine Book PDF" in source
    assert "Download Full Magazine ZIP" in source
    assert "Download Full Magazine Page" in source
