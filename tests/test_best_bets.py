from __future__ import annotations

import unittest

import pandas as pd

from autonomous_betting_agent.best_bets import apply_best_bet_layer, rank_best_bets


class BestBetsTests(unittest.TestCase):
    def test_qualified_candidate_with_independent_edge(self) -> None:
        frame = pd.DataFrame([
            {
                "Event": "Away at Home",
                "Start": "2026-01-01",
                "Prediction": "Home",
                "Sport": "mlb",
                "Market probability": "60%",
                "ARA model probability": "68%",
                "Classification": "Strong",
                "Data quality": 95,
                "Risk penalty": 5,
                "Best price": 1.80,
                "Books": 10,
            }
        ])
        enriched = apply_best_bet_layer(frame)
        self.assertIn(enriched.iloc[0]["aba_best_bet_status"], {"QUALIFIED", "QUALIFIED_STRONG"})
        self.assertGreaterEqual(float(enriched.iloc[0]["aba_best_bet_score"]), 75)

    def test_heavy_favorite_is_rejected(self) -> None:
        frame = pd.DataFrame([
            {
                "Event": "Away at Home",
                "Start": "2026-01-01",
                "Prediction": "Home",
                "Sport": "mlb",
                "Market probability": "92%",
                "ARA model probability": "95%",
                "Classification": "Strong",
                "Data quality": 95,
                "Risk penalty": 5,
                "Best price": 1.08,
                "Books": 10,
            }
        ])
        enriched = apply_best_bet_layer(frame)
        self.assertEqual(enriched.iloc[0]["aba_best_bet_status"], "REJECT")
        self.assertIn("heavy_favorite_price_under_1_30", enriched.iloc[0]["aba_best_bet_reasons"])

    def test_weather_location_mismatch_is_rejected(self) -> None:
        frame = pd.DataFrame([
            {
                "Event": "Team A at Team B",
                "Start": "2026-01-01",
                "Prediction": "Team B",
                "Sport": "soccer",
                "Market probability": "60%",
                "ARA model probability": "68%",
                "Classification": "Strong",
                "Data quality": 95,
                "Risk penalty": 5,
                "Best price": 1.80,
                "Books": 10,
                "weather_tier": "Low",
                "weather_location_query": "Osnabrück, Germany",
                "weather_location": "New Germany, Minnesota, United States of America",
            }
        ])
        enriched = apply_best_bet_layer(frame)
        self.assertEqual(enriched.iloc[0]["aba_best_bet_status"], "REJECT")
        self.assertIn("weather_location_mismatch", enriched.iloc[0]["aba_best_bet_reasons"])

    def test_missing_model_probability_is_track_only(self) -> None:
        frame = pd.DataFrame([
            {
                "Event": "Away at Home",
                "Start": "2026-01-01",
                "Prediction": "Home",
                "Sport": "mlb",
                "Market probability": "60%",
                "Classification": "Strong",
                "Data quality": 95,
                "Risk penalty": 5,
                "Best price": 1.80,
                "Books": 10,
            }
        ])
        enriched = apply_best_bet_layer(frame)
        self.assertEqual(enriched.iloc[0]["aba_best_bet_status"], "TRACK_ONLY_NEEDS_MODEL_PROBABILITY")

    def test_rank_best_bets_dedupes_and_sorts(self) -> None:
        frame = pd.DataFrame([
            {"Event": "A at B", "Start": "2026-01-01", "Prediction": "B", "Sport": "mlb", "Market probability": "60%", "ARA model probability": "68%", "Classification": "Strong", "Data quality": 95, "Risk penalty": 5, "Best price": 1.80, "Books": 10},
            {"Event": "A at B", "Start": "2026-01-01", "Prediction": "B", "Sport": "mlb", "Market probability": "60%", "ARA model probability": "68%", "Classification": "Strong", "Data quality": 95, "Risk penalty": 5, "Best price": 1.80, "Books": 10},
        ])
        ranked = rank_best_bets(frame, top_n=10)
        self.assertEqual(len(ranked), 1)
        self.assertTrue(str(ranked.iloc[0]["aba_best_bet_status"]).startswith("QUALIFIED"))


if __name__ == "__main__":
    unittest.main()
