from __future__ import annotations

import pandas as pd

from autonomous_betting_agent.report_product_layer import MagazineBrand
from autonomous_betting_agent.report_studio_service import ReportStudioFilters, build_report_studio_state, report_studio_summary


def sample_rows() -> pd.DataFrame:
    return pd.DataFrame([
        {"event": "Official Edge", "sport": "MLB", "prediction": "Moneyline: A", "learned_model_probability": 0.62, "decimal_price": 2.10, "odds_source": "The Odds API", "proof_id": "P1", "grade": "WIN"},
        {"event": "High Probability Research", "sport": "Boxing", "prediction": "Game total: Over 10.5", "learned_model_probability": 0.745, "decimal_price": 1.30, "odds_source": "The Odds API", "grade": "WIN"},
        {"event": "Negative Edge Loss", "sport": "Soccer", "prediction": "Game total: Under 2.5", "learned_model_probability": 0.70, "decimal_price": 1.40, "odds_source": "The Odds API", "grade": "LOSS"},
        {"event": "Missing Odds", "sport": "WNBA", "prediction": "Moneyline: B", "learned_model_probability": 0.66, "odds_source": "api limit", "grade": "PENDING"},
        {"event": "Unsupported Tennis", "sport": "tennis", "prediction": "Moneyline: C", "learned_model_probability": 0.72, "decimal_price": 2.00, "odds_source": "The Odds API", "grade": "WIN"},
    ])


def run_smoke_test() -> None:
    brand = MagazineBrand(brand_name="ABA Signal Pro", report_title="Studio Service Smoke Test", workspace_id="studio_service_test")
    state = build_report_studio_state(sample_rows(), brand, filters=ReportStudioFilters(max_rows=75, language="en", mode="consumer"), source_note="smoke")
    summary = report_studio_summary(state)
    assert summary["raw_rows"] == 5
    assert summary["cards"] == 5
    assert summary["official_publish_ready"] == 1
    assert summary["client_report_ready"] == 3
    assert summary["learning_ready"] == 3
    assert summary["data_issues"] == 2
    assert state.exports.pdf_bytes.startswith(b"%PDF")
    assert state.exports.html
    assert state.exports.whatsapp
    assert state.exports.feed["schema_version"] == "aba-report-feed-v2"
    assert "by_edge_bucket" in state.audit
    assert not state.audit["negative_edge_winners"].empty

    filtered = build_report_studio_state(sample_rows(), brand, filters=ReportStudioFilters(selected_sports=("MLB",), max_rows=75))
    filtered_summary = report_studio_summary(filtered)
    assert filtered_summary["cards"] == 1
    assert filtered_summary["official_publish_ready"] == 1


if __name__ == "__main__":
    run_smoke_test()
    print("report studio service smoke test passed")
