from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.learning import (
    GradedPrediction,
    ProbabilityCalibrator,
    evaluate,
    fit_probability_calibrator,
    parse_graded_csv,
)


class LearningTests(unittest.TestCase):
    def test_fit_probability_calibrator_improves_or_preserves_brier(self) -> None:
        rows = [
            GradedPrediction("a", 0.70, 1),
            GradedPrediction("b", 0.65, 1),
            GradedPrediction("c", 0.62, 1),
            GradedPrediction("d", 0.58, 0),
            GradedPrediction("e", 0.55, 0),
            GradedPrediction("f", 0.53, 1),
            GradedPrediction("g", 0.72, 0),
            GradedPrediction("h", 0.60, 1),
        ]
        before = evaluate(rows)["brier"]
        calibrator = fit_probability_calibrator(rows, epochs=50, min_events=5)
        after = evaluate(rows, calibrator)["brier"]
        self.assertEqual(calibrator.events_trained, len(rows))
        self.assertLessEqual(after, before + 0.05)

    def test_calibrator_round_trip(self) -> None:
        calibrator = ProbabilityCalibrator(intercept=-0.1, slope=0.9, events_trained=12)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "learned_state.json"
            calibrator.save(path)
            loaded = ProbabilityCalibrator.load(path)
        self.assertEqual(loaded.events_trained, 12)
        self.assertAlmostEqual(loaded.apply(0.6), calibrator.apply(0.6))

    def test_parse_graded_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.csv"
            path.write_text(
                "event_name,prediction,probability,result\n"
                "Game A,Team A,64.3%,won\n"
                "Game B,Team B,0.57,lost\n",
                encoding="utf-8",
            )
            rows = parse_graded_csv(path)
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[0].probability, 0.643)
        self.assertEqual(rows[0].outcome, 1)
        self.assertEqual(rows[1].outcome, 0)


if __name__ == "__main__":
    unittest.main()
