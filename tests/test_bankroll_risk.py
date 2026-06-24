from __future__ import annotations

from autonomous_betting_agent.bankroll import suggest_stake


def test_bad_audit_blocks_stake():
    suggestion = suggest_stake({"odds_audit_status": "fail", "model_probability": 0.6, "decimal_price": 1.9}, bankroll=100)
    assert suggestion.blocked
    assert suggestion.stake == 0


def test_missing_probability_or_odds_blocks_stake():
    suggestion = suggest_stake({"model_probability": 0.6}, bankroll=100)
    assert suggestion.blocked
    assert suggestion.stake == 0


def test_exposure_cap_limits_flat_stake():
    suggestion = suggest_stake(
        {"model_probability": 0.6, "decimal_price": 2.0, "odds_audit_status": "pass"},
        bankroll=100,
        mode="flat",
        flat_units=10,
        max_daily_exposure_pct=0.05,
        max_event_exposure_pct=0.05,
    )
    assert suggestion.stake == 5


def test_conservative_kelly_positive_edge_suggests_stake():
    suggestion = suggest_stake(
        {"model_probability": 0.6, "decimal_price": 2.1, "odds_audit_status": "pass"},
        bankroll=100,
        mode="conservative_kelly",
        max_daily_exposure_pct=0.25,
        max_event_exposure_pct=0.25,
    )
    assert not suggestion.blocked
    assert suggestion.stake > 0
