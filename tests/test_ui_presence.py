from __future__ import annotations

import unittest
from pathlib import Path


class UiPresenceTests(unittest.TestCase):
    def test_streamlit_app_imports_pro_predictor_page(self) -> None:
        text = Path("streamlit_app.py").read_text(encoding="utf-8")
        self.assertIn("import pages.pro_predictor", text)
        self.assertIn("mobile_safe_file_uploader", text)
        self.assertIn("st.file_uploader = mobile_safe_file_uploader", text)
        self.assertNotIn("runpy.run_path", text)
        self.assertNotIn("PRO_PREDICTOR_PAGE", text)

    def test_pro_predictor_has_direct_upload_fix(self) -> None:
        text = Path("pages/pro_predictor.py").read_text(encoding="utf-8")
        self.assertIn("direct-upload-fix-v9", text)
        self.assertIn("Upload ARA learning memory file", text)
        self.assertIn("type=None", text)
        self.assertIn("direct_page_memory_upload_v9", text)
        self.assertIn("Paste ARA learning memory CSV here", text)
        self.assertIn("direct_page_memory_paste_v9", text)

    def test_standalone_pages_contain_fields(self) -> None:
        market = Path("market_capture_page.py").read_text(encoding="utf-8")
        context = Path("context_layer_page.py").read_text(encoding="utf-8")
        self.assertIn("Language / Idioma", market)
        self.assertIn("odds_api_key", market)
        self.assertIn("book_regions", market)
        self.assertIn("max_api_calls", market)
        self.assertIn("Language / Idioma", context)
        self.assertIn("weatherapi_key", context)
        self.assertIn("sportsdataio_key", context)
        self.assertIn("manual_weather", context)


if __name__ == "__main__":
    unittest.main()
