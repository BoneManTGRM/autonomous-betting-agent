from __future__ import annotations

from autonomous_betting_agent.target_mode import (
    TargetModePolicy,
    estimated_ev,
    evaluate_target_mode,
    implied_probability,
    price_probability_gap,
)


def clean_row(**overrides):
    row = {
        "final_probability_value": 0.70,
        "market_probability_value": 0.68,
        "books": 5,
        "reliability_score": 97.0,
        "price_probability_gap_value": 0.03,
        "estimated_ev_value": 0.05,
        "duplicate_event_pick": False,
        "market_type": "h2h",
        "confidence": "high",
    }
    row.update(overrides)
    return row


def test_implied_probability_and_gap() -> None:
    assert round(implied_probability(2.0), 4) == 0.5
    assert implied_probability(1.0) is None
    assert round(price_probability_gap(2.0, 0.55), 4) == 0.05


def test_estimated_ev() -> None:
    assert round(estimated_ev(0.70, 1.55), 4) == 0.085
    assert estimated_ev(0.70, 1.0) is None


def test_target_mode_passes_clean_70_candidate() -> None:
    result = evaluate_target_mode(clean_row())
    assert result.passed is True
    assert result.rejection_reason == ""
    assert result.quality_score >= 90


def test_target_mode_rejects_outside_probability_band() -> None:
    result = evaluate_target_mode(clean_row(final_probability_value=0.735))
    assert result.passed is False
    assert "outside 69%-71% band" in result.rejection_reason


def test_target_mode_rejects_low_market_probability() -> None:
    result = evaluate_target_mode(clean_row(market_probability_value=0.55))
    assert result.passed is False
    assert "market probability below floor" in result.rejection_reason


def test_target_mode_rejects_low_books_and_reliability() -> None:
    result = evaluate_target_mode(clean_row(books=2, reliability_score=80.0))
    assert result.passed is False
    assert "not enough books" in result.rejection_reason
    assert "reliability below target" in result.rejection_reason


def test_target_mode_rejects_price_mismatch_and_negative_ev() -> None:
    result = evaluate_target_mode(clean_row(price_probability_gap_value=0.20, estimated_ev_value=-0.03))
    assert result.passed is False
    assert "price/probability mismatch" in result.rejection_reason
    assert "EV below target" in result.rejection_reason


def test_target_mode_rejects_duplicate_or_non_h2h_or_not_high() -> None:
    result = evaluate_target_mode(clean_row(duplicate_event_pick=True, market_type="spreads", confidence="medium"))
    assert result.passed is False
    assert "duplicate event/pick" in result.rejection_reason
    assert "not h2h" in result.rejection_reason
    assert "not high confidence" in result.rejection_reason


def test_policy_can_relax_probability_band() -> None:
    policy = TargetModePolicy(tolerance=0.03)
    result = evaluate_target_mode(clean_row(final_probability_value=0.72), policy)
    assert result.passed is True
