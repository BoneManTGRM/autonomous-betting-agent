import unittest
from datetime import datetime, timezone

import pandas as pd

from autonomous_betting_agent.agent_decision_engine import (
    agent_decision_summary,
    build_agent_decisions,
    evaluate_row,
    event_timing_status,
    lock_ready_candidates,
    playable_candidates,
)
from autonomous_betting_agent.prediction_snapshot import build_prediction_snapshots


class AgentDecisionEngineTests(unittest.TestCase):
    def test_strong_play_requires_positive_edge_and_clean_fields(self):
        row = {
            'event': 'Team A at Team B',
            'sport': 'Demo',
            'market_type': 'moneyline',
            'prediction': 'Team B',
            'model_probability': 0.70,
            'decimal_price': 2.00,
            'bookmaker': 'DemoBook',
            'odds_source': 'DemoOdds',
            'prediction_timestamp': '2026-06-15T18:00:00Z',
            'event_start_utc': '2026-06-15T22:00:00Z',
        }
        result = evaluate_row(row, now_utc=datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc))
        self.assertEqual(result['agent_decision'], 'play_strong')
        self.assertEqual(result['event_timing_status'], 'prediction_before_start')
        self.assertGreater(result['model_market_edge'], 0)
        self.assertTrue(result['lock_ready'])
        self.assertTrue(result['already_locked'])
        self.assertGreater(result['recommended_stake_units'], 0)

    def test_missing_probability_is_review_needed(self):
        row = {
            'event': 'Team A at Team B',
            'prediction': 'Team B',
            'decimal_price': 2.00,
        }
        result = evaluate_row(row)
        self.assertEqual(result['agent_decision'], 'review_needed')
        self.assertIn('missing_model_probability', result['decision_reasons'])

    def test_negative_edge_is_no_action(self):
        row = {
            'event': 'Team A at Team B',
            'sport': 'Demo',
            'market_type': 'moneyline',
            'prediction': 'Team B',
            'model_probability': 0.45,
            'decimal_price': 2.00,
            'bookmaker': 'DemoBook',
            'odds_source': 'DemoOdds',
            'prediction_timestamp': '2026-06-15T18:00:00Z',
            'event_start_utc': '2026-06-15T22:00:00Z',
        }
        result = evaluate_row(row, now_utc=datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc))
        self.assertEqual(result['agent_decision'], 'no_action')
        self.assertIn('negative_edge', result['decision_reasons'])

    def test_missing_source_forces_watch_only_not_play(self):
        row = {
            'event': 'Team A at Team B',
            'sport': 'Demo',
            'market_type': 'moneyline',
            'prediction': 'Team B',
            'model_probability': 0.70,
            'decimal_price': 2.00,
            'prediction_timestamp': '2026-06-15T18:00:00Z',
            'event_start_utc': '2026-06-15T22:00:00Z',
        }
        result = evaluate_row(row, now_utc=datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc))
        self.assertEqual(result['agent_decision'], 'watch_only')
        self.assertIn('missing_bookmaker', result['decision_reasons'])
        self.assertIn('missing_odds_source', result['decision_reasons'])

    def test_timing_guards_block_after_start_and_historical_rows(self):
        after_start = {
            'event': 'Team A at Team B',
            'sport': 'Demo',
            'market_type': 'moneyline',
            'prediction': 'Team B',
            'model_probability': 0.70,
            'decimal_price': 2.00,
            'bookmaker': 'DemoBook',
            'odds_source': 'DemoOdds',
            'prediction_timestamp': '2026-06-15T23:00:00Z',
            'event_start_utc': '2026-06-15T22:00:00Z',
        }
        result = evaluate_row(after_start, now_utc=datetime(2026, 6, 15, 23, 30, tzinfo=timezone.utc))
        self.assertEqual(result['event_timing_status'], 'prediction_timestamp_not_before_start')
        self.assertEqual(result['agent_decision'], 'no_action')

        historical = dict(after_start)
        historical['prediction_timestamp'] = '2026-06-15T18:00:00Z'
        historical['result_status'] = 'win'
        result = evaluate_row(historical, now_utc=datetime(2026, 6, 16, 1, 0, tzinfo=timezone.utc))
        self.assertEqual(result['agent_decision'], 'no_action')
        self.assertIn('historical_result_present', result['decision_reasons'])

    def test_event_timing_status_future_unlocked(self):
        row = {'event_start_utc': '2026-06-15T22:00:00Z'}
        status = event_timing_status(row, now_utc=datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc))
        self.assertEqual(status, 'future_event_not_locked_yet')

    def test_thresholds_flow_to_summary_and_candidate_exports(self):
        frame = pd.DataFrame([
            {
                'event': 'Team A at Team B',
                'sport': 'Demo',
                'market_type': 'moneyline',
                'prediction': 'Team B',
                'model_probability': 0.56,
                'decimal_price': 2.00,
                'bookmaker': 'DemoBook',
                'odds_source': 'DemoOdds',
                'prediction_timestamp': '2026-06-15T18:00:00Z',
                'event_start_utc': '2026-06-15T22:00:00Z',
            }
        ])
        loose = agent_decision_summary(frame, min_edge=0.03, strong_edge=0.10)
        strict = agent_decision_summary(frame, min_edge=0.10, strong_edge=0.15)
        self.assertEqual(loose['play_small'], 1)
        self.assertEqual(strict['watch_only'], 1)
        self.assertEqual(len(playable_candidates(frame, min_edge=0.03, strong_edge=0.10)), 1)
        self.assertEqual(len(lock_ready_candidates(frame, min_edge=0.03, strong_edge=0.10)), 1)

    def test_decisions_frame_and_snapshot_timestamp_protection(self):
        frame = pd.DataFrame([
            {
                'event': 'Team A at Team B',
                'sport': 'Demo',
                'market_type': 'moneyline',
                'prediction': 'Team B',
                'model_probability': 0.70,
                'decimal_price': 2.00,
                'bookmaker': 'DemoBook',
                'odds_source': 'DemoOdds',
                'known_start_utc': '2026-06-15T22:00:00Z',
            }
        ])
        decisions = build_agent_decisions(frame, now_utc=datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc))
        self.assertEqual(len(decisions), 1)
        self.assertIn('not_locked_yet', decisions.loc[0, 'decision_signals'])
        self.assertTrue(decisions.loc[0, 'lock_ready'])
        snapshots = build_prediction_snapshots(frame, allow_auto_lock=False)
        self.assertEqual(snapshots.loc[0, 'locked_at_utc'], '')
        self.assertEqual(snapshots.loc[0, 'lock_status'], 'not_official')


if __name__ == '__main__':
    unittest.main()
