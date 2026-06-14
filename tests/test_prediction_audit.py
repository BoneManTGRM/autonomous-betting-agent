from __future__ import annotations

import unittest

import pandas as pd

from autonomous_betting_agent.prediction_audit import audit_predictions


class PredictionAuditTests(unittest.TestCase):
    def test_audit_marks_duplicates_and_summarizes_results(self) -> None:
        frame = pd.DataFrame([
            {"Event": "A at B", "Start": "2026-01-01", "Prediction": "B", "Sport": "mlb", "Market probability": "60%", "ARA model probability": "68%", "Classification": "Strong", "Data quality": 95, "Risk penalty": 5, "Best price": 1.80, "Books": 10, "result": "won"},
            {"Event": "A at B", "Start": "2026-01-01", "Prediction": "B", "Sport": "mlb", "Market probability": "60%", "ARA model probability": "68%", "Classification": "Strong", "Data quality": 95, "Risk penalty": 5, "Best price": 1.80, "Books": 10, "result": "won"},
            {"Event": "C at D", "Start": "2026-01-02", "Prediction": "D", "Sport": "mlb", "Market probability": "60%", "ARA model probability": "68%", "Classification": "Strong", "Data quality": 95, "Risk penalty": 5, "Best price": 1.80, "Books": 10, "result": "lost"},
        ])
        checked, deduped, report = audit_predictions(frame)
        self.assertEqual(len(checked), 3)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(int(checked["aba_audit_is_duplicate"].sum()), 2)
        self.assertEqual(report["raw"]["wins"], 2)
        self.assertEqual(report["raw"]["losses"], 1)
        self.assertAlmostEqual(report["raw"]["unit_profit_loss"], 0.6)
        self.assertIn("qualified_rows", report)

    def test_audit_keeps_weather_location_mismatch_visible(self) -> None:
        frame = pd.DataFrame([
            {"Event": "Team A at Team B", "Start": "2026-01-01", "Prediction": "Team B", "Sport": "soccer", "Market probability": "60%", "ARA model probability": "68%", "Classification": "Strong", "Data quality": 95, "Risk penalty": 5, "Best price": 1.80, "Books": 10, "location_query": "London, England", "location_name": "England", "region": "Oppland", "country": "Norway"},
        ])
        checked, _, report = audit_predictions(frame)
        self.assertEqual(checked.iloc[0]["aba_best_bet_status"], "REJECT")
        self.assertIn("weather_location_mismatch", checked.iloc[0]["aba_best_bet_reasons"])
        self.assertGreaterEqual(report["risk_flag_counts"].get("weather_location_mismatch", 0), 1)

    def test_audit_reports_price_bucket_risk(self) -> None:
        frame = pd.DataFrame([
            {"Event": "A", "Start": "2026-01-01", "Prediction": "A", "Sport": "mlb", "Market probability": "92%", "ARA model probability": "96%", "Classification": "Strong", "Data quality": 95, "Risk penalty": 5, "Best price": 1.05, "Books": 10, "result": "won"},
            {"Event": "B", "Start": "2026-01-02", "Prediction": "B", "Sport": "mlb", "Market probability": "84%", "ARA model probability": "90%", "Classification": "Strong", "Data quality": 95, "Risk penalty": 5, "Best price": 1.18, "Books": 10, "result": "won"},
            {"Event": "C", "Start": "2026-01-03", "Prediction": "C", "Sport": "mlb", "Market probability": "78%", "ARA model probability": "86%", "Classification": "Strong", "Data quality": 95, "Risk penalty": 5, "Best price": 1.28, "Books": 10, "result": "lost"},
            {"Event": "D", "Start": "2026-01-04", "Prediction": "D", "Sport": "mlb", "Market probability": "58%", "ARA model probability": "67%", "Classification": "Strong", "Data quality": 95, "Risk penalty": 5, "Best price": 1.75, "Books": 10, "result": "won"},
        ])
        checked, _, report = audit_predictions(frame)
        self.assertIn("aba_audit_price_bucket", checked.columns)
        self.assertEqual(report["price_stats"]["under_1_30_rows"], 3)
        self.assertEqual(report["price_bucket_counts"]["under_1_10"], 1)
        self.assertEqual(report["price_bucket_counts"]["1_10_to_1_19"], 1)
        self.assertEqual(report["price_bucket_counts"]["1_20_to_1_29"], 1)
        self.assertEqual(report["price_bucket_performance_raw"]["1_20_to_1_29"]["losses"], 1)
        self.assertAlmostEqual(report["price_bucket_performance_raw"]["1_50_to_1_99"]["unit_profit_loss"], 0.75)

    def test_empty_audit_report_has_stable_keys(self) -> None:
        checked, deduped, report = audit_predictions(pd.DataFrame())
        self.assertEqual(len(checked), 0)
        self.assertEqual(len(deduped), 0)
        for key in (
            "raw",
            "deduped",
            "status_counts",
            "grade_counts",
            "risk_flag_counts",
            "duplicate_rows",
            "qualified_rows",
            "rejected_rows",
            "price_stats",
            "price_bucket_counts",
            "price_bucket_performance_raw",
            "price_bucket_performance_deduped",
        ):
            self.assertIn(key, report)
        self.assertEqual(report["duplicate_rows"], 0)
        self.assertEqual(report["price_stats"]["priced_rows"], 0)


if __name__ == "__main__":
    unittest.main()
