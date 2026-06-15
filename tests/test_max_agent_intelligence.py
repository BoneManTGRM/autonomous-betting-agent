import unittest

import pandas as pd

from autonomous_betting_agent.api_snapshot_memory import build_api_snapshots, snapshot_memory_summary
from autonomous_betting_agent.clv_intelligence import build_clv_intelligence, clv_summary
from autonomous_betting_agent.post_loss_autopsy import build_loss_autopsies, future_rules
from autonomous_betting_agent.sport_specific_models import build_sport_specific_decisions, sport_key, sport_model_summary
from autonomous_betting_agent.walk_forward_lab import walk_forward_summary, walk_forward_validate


class MaxAgentIntelligenceTests(unittest.TestCase):
    def sample_frame(self):
        rows = []
        for idx in range(12):
            won = idx % 3 != 0
            rows.append({
                'event': f'Team {idx} at Team {idx + 1}',
                'sport': 'Tennis' if idx % 2 == 0 else 'NFL',
                'market_type': 'moneyline',
                'prediction': f'Team {idx + 1}',
                'model_probability': 0.64 if won else 0.72,
                'decimal_price': 1.90,
                'closing_decimal_price': 1.80 if won else 2.05,
                'bookmaker': 'DemoBook',
                'odds_source': 'DemoOdds',
                'prediction_timestamp': f'2026-06-{idx + 1:02d}T18:00:00Z',
                'event_start_utc': f'2026-06-{idx + 1:02d}T22:00:00Z',
                'result_status': 'win' if won else 'loss',
                'winner': f'Team {idx + 1}' if won else f'Team {idx}',
                'profit_units': 0.9 if won else -1,
                'injury_status': 'clean',
                'weather_note': 'none',
            })
        return pd.DataFrame(rows)

    def test_api_snapshot_memory(self):
        frame = self.sample_frame()
        snapshots = build_api_snapshots(frame, created_at_utc='2026-06-20T00:00:00Z')
        self.assertEqual(len(snapshots), len(frame))
        self.assertIn('api_snapshot_hash', snapshots.columns)
        summary = snapshot_memory_summary(frame)
        self.assertEqual(summary['rows'], len(frame))
        self.assertGreater(summary['avg_core_coverage'], 0)

    def test_post_loss_autopsy_and_future_rules(self):
        frame = self.sample_frame()
        autopsies = build_loss_autopsies(frame)
        self.assertGreater(len(autopsies), 0)
        self.assertIn('future_rule', autopsies.columns)
        rules = future_rules(frame)
        self.assertGreater(len(rules), 0)

    def test_clv_intelligence(self):
        frame = self.sample_frame()
        clv = build_clv_intelligence(frame)
        self.assertEqual(len(clv), len(frame))
        summary = clv_summary(frame)
        self.assertGreater(summary['ready'], 0)
        self.assertIn('beat_close_rate', summary)

    def test_walk_forward_lab(self):
        frame = self.sample_frame()
        results = walk_forward_validate(frame, min_train_rows=3)
        self.assertGreater(len(results), 0)
        summary = walk_forward_summary(frame, min_train_rows=3)
        self.assertGreater(summary['tested_rows'], 0)
        self.assertIn('avg_brier_walk_forward', summary)

    def test_sport_specific_models(self):
        frame = self.sample_frame()
        self.assertEqual(sport_key('NFL'), 'football')
        self.assertEqual(sport_key('FIFA'), 'soccer')
        decisions = build_sport_specific_decisions(frame)
        self.assertEqual(len(decisions), len(frame))
        self.assertIn('sport_model_key', decisions.columns)
        summary = sport_model_summary(frame)
        self.assertFalse(summary.empty)


if __name__ == '__main__':
    unittest.main()
