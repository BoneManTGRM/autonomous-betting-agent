from __future__ import annotations

import pandas as pd

from autonomous_betting_agent.auto_result_sync import apply_fuzzy_result_updates, pending_sport_keys


def _locked_row(**extra):
    row = {
        'proof_id': 'P1',
        'locked_at_utc': '2026-01-01T00:00:00Z',
        'event_start_utc': '2026-01-02T00:00:00Z',
        'event': 'Away Team at Home Team',
        'sport': 'Basketball',
        'sport_key': 'basketball_nba',
        'market_type': 'h2h',
        'prediction': 'Home Team',
        'decimal_price': 1.80,
        'stake_units': 1.0,
        'result_status': 'pending',
    }
    row.update(extra)
    return row


def _result_row(**extra):
    row = {
        'event': 'Away Team at Home Team',
        'sport': 'Basketball',
        'sport_key': 'basketball_nba',
        'event_start_utc': '2026-01-02T00:00:00Z',
        'home_team': 'Home Team',
        'away_team': 'Away Team',
        'home_score': 100,
        'away_score': 90,
        'winner': 'Home Team',
        'final_score': 'Away Team 90 - 100 Home Team',
    }
    row.update(extra)
    return row


def test_h2h_win_updates_status_and_profit():
    updated, stats = apply_fuzzy_result_updates(pd.DataFrame([_locked_row()]), pd.DataFrame([_result_row()]))
    assert stats['updated_rows'] == 1
    assert stats['wins_added'] == 1
    assert updated.iloc[0]['result_status'] == 'win'
    assert float(updated.iloc[0]['profit_units']) == 0.8


def test_h2h_loss_updates_status():
    updated, stats = apply_fuzzy_result_updates(
        pd.DataFrame([_locked_row(prediction='Away Team')]),
        pd.DataFrame([_result_row()]),
    )
    assert stats['updated_rows'] == 1
    assert stats['losses_added'] == 1
    assert updated.iloc[0]['result_status'] == 'loss'
    assert float(updated.iloc[0]['profit_units']) == -1.0


def test_spread_push_marks_void():
    updated, stats = apply_fuzzy_result_updates(
        pd.DataFrame([_locked_row(market_type='spreads', prediction='Home Team', line_point=-10)]),
        pd.DataFrame([_result_row(home_score=100, away_score=90)]),
    )
    assert stats['updated_rows'] == 1
    assert stats['voids_added'] == 1
    assert updated.iloc[0]['result_status'] == 'void'
    assert float(updated.iloc[0]['profit_units']) == 0.0


def test_total_under_win():
    updated, stats = apply_fuzzy_result_updates(
        pd.DataFrame([_locked_row(market_type='totals', prediction='Under', line_point=195)]),
        pd.DataFrame([_result_row(home_score=100, away_score=90)]),
    )
    assert stats['updated_rows'] == 1
    assert updated.iloc[0]['result_status'] == 'win'


def test_pending_sport_keys_ignores_resolved():
    keys = pending_sport_keys(pd.DataFrame([
        _locked_row(proof_id='P1', sport_key='basketball_nba', result_status='pending'),
        _locked_row(proof_id='P2', sport_key='soccer_mexico_ligamx', result_status='win'),
    ]))
    assert keys == ['basketball_nba']
