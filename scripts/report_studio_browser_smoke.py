from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


SAMPLE_ROWS = [
    {
        "event": "Official Edge",
        "sport": "MLB",
        "prediction": "Moneyline: A",
        "learned_model_probability": 0.62,
        "decimal_price": 2.10,
        "odds_source": "The Odds API",
        "proof_id": "P1",
        "grade": "WIN",
    },
    {
        "event": "High Probability Winner",
        "sport": "Boxing",
        "prediction": "Game total: Over 10.5",
        "learned_model_probability": 0.745,
        "decimal_price": 1.30,
        "odds_source": "The Odds API",
        "grade": "WIN",
    },
    {
        "event": "Missing Odds",
        "sport": "WNBA",
        "prediction": "Moneyline: B",
        "learned_model_probability": 0.66,
        "odds_source": "api limit",
        "grade": "PENDING",
    },
    {
        "event": "Unsupported Tennis",
        "sport": "tennis",
        "prediction": "Moneyline: C",
        "learned_model_probability": 0.72,
        "decimal_price": 2.00,
        "odds_source": "The Odds API",
        "grade": "WIN",
    },
]


def _sample_csv() -> Path:
    path = Path(tempfile.gettempdir()) / "report_studio_browser_sample.csv"
    pd.DataFrame(SAMPLE_ROWS).to_csv(path, index=False)
    return path


def _candidate_urls(base_url: str) -> list[str]:
    root = base_url.rstrip("/")
    if root.endswith("report_studio"):
        return [root, root.rsplit("/", 1)[0]]
    return [f"{root}/report_studio", root]


def _open_report_studio(page, base_url: str) -> None:
    last_error: Exception | None = None
    for url in _candidate_urls(base_url):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(4000)
            body = page.locator("body").inner_text(timeout=10000)
            if "Report Studio" in body or "Estudio de Reportes" in body:
                return
        except (PlaywrightError, PlaywrightTimeoutError) as exc:
            last_error = exc
    raise RuntimeError(f"Report Studio did not load from candidates: {_candidate_urls(base_url)}; last_error={last_error}")


def run_browser_smoke() -> None:
    base_url = os.environ.get("REPORT_STUDIO_BASE_URL", "http://127.0.0.1:8501")
    sample = _sample_csv()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        try:
            _open_report_studio(page, base_url)
            file_input = page.locator("input[type='file']").first
            file_input.set_input_files(str(sample), timeout=20000)
            page.wait_for_timeout(8000)
            body = page.locator("body").inner_text(timeout=20000)
            forbidden = [
                "StreamlitDuplicateElementId",
                "Traceback",
                "Exception",
                "DuplicateElementId",
            ]
            for token in forbidden:
                assert token not in body, f"Browser smoke found Streamlit error token: {token}"
            required = ["Premium Cards", "Magazine Report", "WhatsApp", "Analyst Proof", "Exports", "Images", "App Feed", "Diagnostics"]
            missing = [token for token in required if token not in body]
            assert not missing, f"Report Studio missing visible tab labels after upload: {missing}"
        finally:
            browser.close()


if __name__ == "__main__":
    run_browser_smoke()
    print("report studio browser smoke test passed")
