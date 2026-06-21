from types import SimpleNamespace
import unittest
from unittest.mock import patch

import pandas as pd

from autonomous_betting_agent.closing_line_tools import collect_closing_lines
from autonomous_betting_agent.odds_lock_tools import lock_rows


class ClosingLineToolsTests(unittest.TestCase):
    def _locked_frame(self):
        return lock_rows(pd.DataFrame([
            {
                'event': 'Away Team at Home Team',
                'sport': 'Basketball',
                'sport_key': 'basketball_nba',
                'market_type': 'h2h',
                'prediction': 'Home Team',
                'model_probability': 0.64,
                'decimal_price': 1.80,
                'bookmaker': 'OpenBook',
                'agent_decision': 'play_small',
                'event_start_utc': '2099-01-01T00:00:00Z',
            }
        ]), analyst='Test Brand')

    def test_collects_closing_price_for_matching_moneyline(self):
        summary = SimpleNamespace(
            sport_key='basketball_nba',
            sport_title='Basketball',
            commence_time='2099-01-01T00:00:00Z',
            away_team='Away Team',
            home_team='Home Team',
            event_id='event-1',
            outcomes=[
                SimpleNamespace(name='Home Team', average_price=1.70, market='h2h', point=None, source_count=6),
                SimpleNamespace(name='Away Team', average_price=2.20, market='h2h', point=None, source_count=6),
            ],
        )
        with patch('autonomous_betting_agent.closing_line_tools.fetch_odds', return_value=[{'id': 'event-1'}]), \
             patch('autonomous_betting_agent.closing_line_tools.summarize_event', return_value=summary):
            updated, stats = collect_closing_lines(self._locked_frame(), api_key='real_key_1234567890', sport_key='basketball_nba')
        self.assertEqual(stats['updated_rows'], 1)
        self.assertEqual(float(updated.iloc[0]['closing_decimal_price']), 1.70)
        self.assertEqual(updated.iloc[0]['closing_source'], 'the_odds_api_current_odds')

    def test_does_not_overwrite_existing_closing_price_by_default(self):
        frame = self._locked_frame()
        frame.loc[0, 'closing_decimal_price'] = 1.66
        summary = SimpleNamespace(
            sport_key='basketball_nba',
            sport_title='Basketball',
            commence_time='2099-01-01T00:00:00Z',
            away_team='Away Team',
            home_team='Home Team',
            event_id='event-1',
            outcomes=[SimpleNamespace(name='Home Team', average_price=1.70, market='h2h', point=None, source_count=6)],
        )
        with patch('autonomous_betting_agent.closing_line_tools.fetch_odds', return_value=[{'id': 'event-1'}]), \
             patch('autonomous_betting_agent.closing_line_tools.summarize_event', return_value=summary):
            updated, stats = collect_closing_lines(frame, api_key='real_key_1234567890', sport_key='basketball_nba')
        self.assertEqual(stats['updated_rows'], 0)
        self.assertEqual(float(updated.iloc[0]['closing_decimal_price']), 1.66)


if __name__ == '__main__':
    unittest.main()
