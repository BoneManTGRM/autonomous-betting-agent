from __future__ import annotations

import unittest

import pandas as pd

from autonomous_betting_agent.buyer_report import buyer_demo_markdown
from autonomous_betting_agent.clv import build_clv_frame, clv_summary
from autonomous_betting_agent.grading_review import build_review_queue, review_status
from autonomous_betting_agent.model_lab import lab_summary, recommendations_from_patterns
from autonomous_betting_agent.prediction_snapshot import build_prediction_snapshots, snapshot_summary, verify_snapshots


class ValueUpgradeTests(unittest.TestCase):
    def test_prediction_snapshot_locks_official_rows(self) -> None:
        frame = pd.DataFrame([
            {'event': 'A at B', 'prediction': 'B', 'model_probability': '70%', 'decimal_price': 1.9, 'bookmaker': 'DemoBook'},
            {'event': 'C at D', 'prediction': 'C', 'model_probability': '', 'decimal_price': ''},
        ])
        snapshots = build_prediction_snapshots(frame, user_id='Cody Test', locked_at_utc='2026-06-15T20:00:00Z')
        summary = snapshot_summary(snapshots)
        self.assertEqual(summary['total'], 2)
        self.assertEqual(summary['official_locked'], 1)
        self.assertEqual(summary['not_official'], 1)
        self.assertTrue(verify_snapshots(snapshots).valid)
        snapshots.loc[0, 'prediction'] = 'tampered'
        self.assertFalse(verify_snapshots(snapshots).valid)

    def test_grading_review_statuses(self) -> None:
        self.assertEqual(review_status({'event': 'A', 'prediction': 'A', 'winner': 'A'})[0], 'ready_to_grade')
        self.assertEqual(review_status({'event': 'A', 'prediction': 'A', 'result_status': 'win'})[0], 'graded_clean')
        self.assertEqual(review_status({'event': 'A', 'prediction': 'A', 'result_status': 'postponed'})[0], 'void')
        queue = build_review_queue(pd.DataFrame([{'event': 'A', 'prediction': 'A', 'winner': 'A'}, {'event': 'B', 'prediction': 'B'}]))
        self.assertEqual(queue.iloc[0]['review_status'], 'ready_to_grade')

    def test_clv_calculation(self) -> None:
        frame = pd.DataFrame([
            {'event': 'A', 'decimal_price': 2.00, 'closing_decimal_price': 1.80},
            {'event': 'B', 'decimal_price': 1.80, 'closing_decimal_price': 2.00},
        ])
        clv = build_clv_frame(frame)
        self.assertTrue(bool(clv.loc[0, 'clv_positive']))
        self.assertFalse(bool(clv.loc[1, 'clv_positive']))
        summary = clv_summary(frame)
        self.assertEqual(summary['with_clv'], 2)
        self.assertEqual(summary['positive_clv'], 1)

    def test_model_lab_recommendations(self) -> None:
        patterns = [
            {'area': 'A', 'records': 10, 'avg_predicted': 0.6, 'actual_hit_rate': 0.8, 'smoothed_hit_rate': 0.72, 'smoothed_edge': 0.12, 'reliability': 0.6},
            {'area': 'B', 'records': 10, 'avg_predicted': 0.7, 'actual_hit_rate': 0.4, 'smoothed_hit_rate': 0.55, 'smoothed_edge': -0.15, 'reliability': 0.5},
        ]
        recs = recommendations_from_patterns(patterns)
        actions = set(recs['recommended_action'])
        self.assertIn('raise_trust', actions)
        self.assertIn('lower_trust', actions)
        summary = lab_summary(recs)
        self.assertEqual(summary['raise_trust'], 1)
        self.assertEqual(summary['lower_trust'], 1)

    def test_buyer_report_generates_markdown(self) -> None:
        ledger = pd.DataFrame([
            {'sport': 'Tennis', 'result_status': 'win', 'stake_units': 1, 'profit_units': 0.9, 'decimal_price': 1.9, 'confidence_tier': 'A+ High Confidence'},
            {'sport': 'Tennis', 'result_status': 'loss', 'stake_units': 1, 'profit_units': -1, 'decimal_price': 2.0, 'confidence_tier': 'A Strong'},
        ])
        report = buyer_demo_markdown(ledger=ledger, memory_summary={'training_mode': 'replace', 'uploaded_usable_rows': 10})
        self.assertIn('Buyer Demo Report', report)
        self.assertIn('Total picks: 2', report)
        self.assertIn('Tennis', report)


if __name__ == '__main__':
    unittest.main()
