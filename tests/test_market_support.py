from __future__ import annotations

from autonomous_betting_agent.market_support import apply_market_support_flags, is_market_supported, market_review_reasons, market_support_status


def test_supported_sport_and_market_passes():
    row = {"sport": "NBA", "market": "moneyline"}
    assert is_market_supported(row)
    assert market_support_status(row)["market_support_status"] == "supported"


def test_tennis_defaults_to_review():
    row = {"sport": "ATP Tennis", "market": "moneyline"}
    status = market_support_status(row)
    assert status["market_support_status"] == "review"
    assert any("Tennis" in reason for reason in status["market_support_reasons"])


def test_tennis_can_be_blocked():
    row = {"sport": "WTA", "market": "moneyline"}
    flagged = apply_market_support_flags(row, tennis_mode="block")
    assert flagged["market_support_status"] == "blocked"
    assert flagged["ledger_type"] == "quarantine"


def test_missing_market_triggers_review():
    row = {"sport": "NBA"}
    assert market_support_status(row)["market_support_status"] == "review"
    assert any("Market type is missing" in reason for reason in market_review_reasons(row))


def test_unsupported_sport_triggers_review():
    row = {"sport": "unknown sport", "market": "moneyline"}
    assert market_support_status(row)["market_support_status"] == "review"
