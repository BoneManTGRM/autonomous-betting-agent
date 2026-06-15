from __future__ import annotations

import unittest

import pandas as pd

from autonomous_betting_agent.data_health import data_health_frame, data_health_score


class DataHealthTests(unittest.TestCase):
    def test_empty_frame_scores_poor(self) -> None:
        result = data_health_score(pd.DataFrame())
        self.assertEqual(result['grade'], 'Poor')
        self.assertEqual(result['score'], 0.0)

    def test_complete_frame_scores_high(self) -> None:
        frame = pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': '70%', 'decimal_price': 1.8, 'api_coverage_score': 1.0, 'result_status': 'win', 'decision': 'strong_candidate', 'clean_grading_status': 'graded_clean'},
            {'event': 'C at D', 'prediction': 'C', 'model_probability': '65%', 'decimal_price': 1.9, 'api_coverage_score': 0.9, 'result_status': 'pending', 'decision': 'candidate', 'clean_grading_status': 'pending'},
        ])
        result = data_health_score(frame)
        self.assertGreaterEqual(result['score'], 80)
        self.assertIn(result['grade'], {'Good', 'Excellent'})

    def test_health_frame_has_checks(self) -> None:
        frame = pd.DataFrame([{'event': 'A at B', 'prediction': 'B'}])
        checks = data_health_frame(frame)
        self.assertIn('name', checks.columns)
        self.assertIn('points', checks.columns)
        self.assertGreater(len(checks), 1)


if __name__ == '__main__':
    unittest.main()
