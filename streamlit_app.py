from __future__ import annotations

from pathlib import Path
import runpy

# Streamlit Cloud can be configured to launch either streamlit_app.py, app.py,
# main.py, or a file inside pages/. Keep the root entrypoint as a thin launcher
# so the main app URL always opens the full live Pro Predictor page.
PRO_PREDICTOR_PAGE = Path(__file__).parent / "pages" / "pro_predictor.py"

if not PRO_PREDICTOR_PAGE.exists():
    raise FileNotFoundError(f"Missing Pro Predictor page: {PRO_PREDICTOR_PAGE}")

runpy.run_path(str(PRO_PREDICTOR_PAGE), run_name="__main__")
