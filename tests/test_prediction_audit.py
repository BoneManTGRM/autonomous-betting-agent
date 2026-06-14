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


if __name__ == "__main__":
    unittest.main()
