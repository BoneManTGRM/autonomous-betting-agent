import unittest

import pandas as pd

from autonomous_betting_agent.four_tool_orchestrator import four_tool_recommendation, page_health


class FourToolOrchestratorTests(unittest.TestCase):
    def test_scanner_rows_are_ready_for_predictor(self):
        frame = pd.DataFrame([
            {
                'event': 'A at B',
                'sport': 'Tennis',
                'market_type': 'h2h',
                'prediction': 'B',
                'decimal_price': 1.91,
                'bookmaker': 'Book',
            }
        ])
        health = page_health(frame, page='scanner_pro')
        self.assertEqual(health['status'], 'ready_for_pro_predictor')
        self.assertEqual(health['next_action'], 'send_to_pro_predictor')
        self.assertEqual(four_tool_recommendation(frame), 'pro_predictor')

    def test_predictor_rows_are_ready_for_what_are_the_odds(self):
        frame = pd.DataFrame([
            {
                'event': 'A at B',
                'sport': 'Tennis',
                'market_type': 'h2h',
                'prediction': 'B',
                'model_probability': 0.64,
                'decimal_price': 2.05,
                'event_start_utc': '2099-01-01T00:00:00Z',
            }
        ])
        health = page_health(frame, page='pro_predictor')
        self.assertEqual(health['status'], 'ready_for_what_are_the_odds')
        self.assertEqual(health['next_action'], 'send_to_what_are_the_odds')
        self.assertEqual(four_tool_recommendation(frame), 'what_are_the_odds')

    def test_value_rows_route_to_lock_or_learning(self):
        frame = pd.DataFrame([
            {
                'event': 'A at B',
                'prediction': 'B',
                'model_probability': 0.64,
                'decimal_price': 2.05,
                'agent_decision': 'play_small',
                'lock_ready': True,
            }
        ])
        health = page_health(frame, page='what_are_the_odds')
        self.assertEqual(health['status'], 'ready_for_lock_or_learning')
        self.assertEqual(health['playable_rows'], 1)

    def test_finished_rows_route_to_learning_memory(self):
        frame = pd.DataFrame([
            {
                'event': f'E{i}',
                'prediction': 'B',
                'model_probability': 0.62,
                'decimal_price': 1.91,
                'result_status': 'win' if i % 2 else 'loss',
            }
            for i in range(6)
        ])
        health = page_health(frame, page='learning_memory')
        self.assertEqual(health['status'], 'ready_to_train')
        self.assertEqual(health['next_action'], 'train_and_save_memory')
        self.assertEqual(four_tool_recommendation(frame), 'learning_memory')


if __name__ == '__main__':
    unittest.main()
