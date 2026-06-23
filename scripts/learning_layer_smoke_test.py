from __future__ import annotations

import pandas as pd

from autonomous_betting_agent.report_learning_layer import apply_learning_layer, calibration_audit
from autonomous_betting_agent.report_product_layer import enrich_rows
from autonomous_betting_agent.report_studio_ui import render_premium_card_deck


def run_smoke_test() -> None:
    rows = pd.DataFrame([
        {'event': 'Official Edge', 'sport': 'MLB', 'prediction': 'Moneyline: A', 'learned_model_probability': 0.62, 'decimal_price': 2.10, 'odds_source': 'The Odds API', 'proof_id': 'P1', 'grade': 'WIN'},
        {'event': 'High Prob Winner', 'sport': 'Boxing', 'prediction': 'Game total: Over 10.5', 'learned_model_probability': 0.745, 'decimal_price': 1.30, 'odds_source': 'The Odds API', 'grade': 'WIN'},
        {'event': 'Missing Odds', 'sport': 'WNBA', 'prediction': 'Moneyline: B', 'learned_model_probability': 0.66, 'odds_source': 'api limit', 'grade': 'PENDING'},
        {'event': 'Unsupported Tennis', 'sport': 'tennis', 'prediction': 'Moneyline: C', 'learned_model_probability': 0.72, 'decimal_price': 2.00, 'odds_source': 'The Odds API', 'grade': 'WIN'},
        {'event': 'Push Row', 'sport': 'MMA', 'prediction': 'Point spread: D +1.5', 'learned_model_probability': 0.58, 'decimal_price': 1.91, 'odds_source': 'The Odds API', 'grade': 'PUSH'},
    ])
    cards = apply_learning_layer(enrich_rows(rows))
    assert bool(cards.loc[0, 'official_publish_ready'])
    assert cards.loc[1, 'result_status'] == 'WIN'
    assert cards.loc[1, 'price_value_label'] == 'Negative at listed odds'
    assert cards.loc[1, 'consumer_action'] == 'Price Watch / Research'
    assert not bool(cards.loc[1, 'official_publish_ready'])
    assert bool(cards.loc[1, 'client_report_ready'])
    assert bool(cards.loc[1, 'learning_ready'])
    assert cards.loc[2, 'data_issue_reason'] == 'Missing or unverified odds'
    assert cards.loc[3, 'data_issue_reason'] == 'Unsupported sport'
    html = render_premium_card_deck(cards)
    assert 'No Play' not in html
    assert 'Price Watch / Research' in html
    audit = calibration_audit(cards, min_sample=1)
    assert 'by_edge_bucket' in audit
    assert not audit['negative_edge_winners'].empty


if __name__ == '__main__':
    run_smoke_test()
    print('learning layer smoke test passed')
