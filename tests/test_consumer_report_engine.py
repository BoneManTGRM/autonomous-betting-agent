import unittest

import pandas as pd

from autonomous_betting_agent.consumer_report_engine import (
    BrandSettings,
    cards_to_json,
    consumer_cards,
    prepare_report_frame,
    render_consumer_cards_html,
    render_magazine_markdown,
)


class ConsumerReportEngineTests(unittest.TestCase):
    def sample_frame(self):
        return pd.DataFrame([
            {
                'event': 'LA Angels vs Toronto Blue Jays',
                'sport': 'Baseball',
                'market_type': 'h2h',
                'prediction': 'Blue Jays ML',
                'model_probability': 0.68,
                'decimal_price': 1.83,
                'bookmaker': 'Book',
                'agent_decision': 'play_small',
                'agent_score': 79,
                'scanner_strength_score': 81,
                'model_edge': 0.045,
                'expected_value_per_unit': 0.08,
                'proof_id': 'OLP-ABC123',
                'proof_status': 'locked_before_start',
                'official_ev_pick': True,
            },
            {
                'event': 'Research Game',
                'sport': 'Soccer',
                'market_type': 'btts',
                'prediction': 'Ambos anotan - No',
                'model_probability': 0.54,
                'decimal_price': 2.4,
                'agent_decision': 'watch_only',
                'official_ev_pick': False,
            },
        ])

    def test_prepare_report_frame_filters_official_rows(self):
        prepared = prepare_report_frame(self.sample_frame(), min_probability=0.60, official_only=True, max_rows=10)
        self.assertEqual(len(prepared), 1)
        self.assertEqual(prepared.iloc[0]['prediction'], 'Blue Jays ML')

    def test_consumer_cards_spanish_output(self):
        brand = BrandSettings(brand_name='Los Reyes', workspace_id='los_reyes', language='es')
        cards = consumer_cards(self.sample_frame().head(1), brand)
        self.assertEqual(cards.iloc[0]['workspace_id'], 'los_reyes')
        self.assertEqual(cards.iloc[0]['brand_name'], 'Los Reyes')
        self.assertEqual(cards.iloc[0]['market'], 'Ganador')
        self.assertIn('modelo', cards.iloc[0]['bullet_1'].lower())
        self.assertEqual(cards.iloc[0]['proof_id'], 'OLP-ABC123')

    def test_magazine_markdown_contains_tendency_and_proof(self):
        brand = BrandSettings(brand_name='Los Reyes', report_title='Reporte', workspace_id='test_01', language='es')
        cards = consumer_cards(self.sample_frame().head(1), brand)
        report = render_magazine_markdown(cards, brand)
        self.assertIn('Tendencia', report)
        self.assertIn('Blue Jays ML', report)
        self.assertIn('OLP-ABC123', report)

    def test_html_escapes_user_content(self):
        frame = pd.DataFrame([{
            'event': '<script>alert(1)</script>',
            'sport': 'Baseball',
            'market_type': 'h2h',
            'prediction': 'Team',
            'model_probability': 0.64,
            'decimal_price': 1.91,
        }])
        brand = BrandSettings(language='en')
        cards = consumer_cards(frame, brand)
        html = render_consumer_cards_html(cards, brand)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)

    def test_json_feed_includes_brand_and_cards(self):
        brand = BrandSettings(brand_name='Tipster Brand', workspace_id='client_a', language='en')
        cards = consumer_cards(self.sample_frame().head(1), brand)
        payload = cards_to_json(cards, brand)
        self.assertIn('Tipster Brand', payload)
        self.assertIn('client_a', payload)
        self.assertIn('Blue Jays ML', payload)


if __name__ == '__main__':
    unittest.main()
