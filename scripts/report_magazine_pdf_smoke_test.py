from __future__ import annotations

import pandas as pd

from autonomous_betting_agent.report_magazine_pdf_service import PDF_HEADER, render_vintage_magazine_pdf
from autonomous_betting_agent.report_product_layer import MagazineBrand, enrich_rows
from autonomous_betting_agent.report_learning_layer_compat import apply_learning_layer_compat


def _sample() -> pd.DataFrame:
    return pd.DataFrame([
        {"event": "LA Angels vs Toronto Blue Jays", "sport": "Baseball", "prediction": "Blue Jays ML", "learned_model_probability": 0.62, "decimal_price": 2.10, "odds_source": "The Odds API", "proof_id": "P1", "grade": "WIN"},
        {"event": "Sao Paulo vs Nacional", "sport": "Futbol", "prediction": "Ambos anotan - No", "learned_model_probability": 0.70, "decimal_price": 1.55, "odds_source": "The Odds API", "grade": "PENDING"},
        {"event": "Missing Odds", "sport": "MMA", "prediction": "Moneyline", "learned_model_probability": 0.66, "odds_source": "api limit", "grade": "PENDING"},
    ])


def run_smoke_test() -> None:
    brand = MagazineBrand(brand_name="ABA Signal Pro", report_title="Magazine Smoke Test", tagline="Premium report")
    cards = apply_learning_layer_compat(enrich_rows(_sample()))
    pdf = render_vintage_magazine_pdf(cards, brand)
    assert pdf.startswith(PDF_HEADER)
    assert len(pdf) > 20000


def main() -> None:
    run_smoke_test()
    print("report magazine PDF smoke test passed")


if __name__ == "__main__":
    main()
