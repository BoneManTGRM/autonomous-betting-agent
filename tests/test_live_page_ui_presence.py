from __future__ import annotations

import unittest
from pathlib import Path


class LivePageUiPresenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = Path('pages/pro_predictor.py').read_text(encoding='utf-8')

    def test_live_pro_predictor_page_has_multi_api_ui(self) -> None:
        self.assertNotIn('Provider key', self.text)
        self.assertIn('Odds API key', self.text)
        self.assertIn('SportsDataIO key', self.text)
        self.assertIn('WeatherAPI key', self.text)
        self.assertIn('Run Pro Predictor', self.text)
        self.assertIn('Loaded from secrets', self.text)
        self.assertIn('LiveAPIContextBuilder', self.text)
        self.assertIn('fuse_row', self.text)

    def test_live_pro_predictor_page_has_current_large_list_workflow(self) -> None:
        self.assertIn('Large-list volume output', self.text)
        self.assertIn('Send large-list volume rows to Odds Lock Pro', self.text)
        self.assertIn('Large-list min agent score', self.text)
        self.assertIn('Download large-list CSV', self.text)
        self.assertIn('pro_predictor_high_confidence_rows', self.text)
        self.assertIn('pro_predictor_latest_rows', self.text)
        self.assertIn('ara_latest_predictions', self.text)
        self.assertIn('persist_handoff', self.text)

    def test_live_pro_predictor_page_has_value_controls(self) -> None:
        self.assertIn('Minimum model probability', self.text)
        self.assertIn('Minimum edge', self.text)
        self.assertIn('Strong edge threshold', self.text)
        self.assertIn('Minimum signal strength', self.text)
        self.assertIn('lock_ready', self.text)
        self.assertIn('agent_decision', self.text)
        self.assertIn('scanner_strength_summary', self.text)

    def test_live_pro_predictor_page_uses_real_api_context_builder(self) -> None:
        self.assertIn('LiveAPIContextBuilder', self.text)
        self.assertIn('context_builder.context_for_event', self.text)
        self.assertIn('api_context', self.text)
        self.assertIn('api_context.update', self.text)
        self.assertIn('fuse_row', self.text)

    def test_live_pro_predictor_page_has_api_coverage_and_date_cutoff(self) -> None:
        self.assertIn('latest_event_date', self.text)
        self.assertIn('parse_event_date', self.text)
        self.assertIn('api_coverage_score', self.text)
        self.assertIn('WeatherAPI', self.text)
        self.assertIn('SportsDataIO', self.text)
        self.assertIn('market_type', self.text)
        self.assertIn('line_point', self.text)


if __name__ == '__main__':
    unittest.main()
