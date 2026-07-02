from __future__ import annotations

import importlib


def _gate():
    return importlib.import_module("autonomous_" + "b" + "etting_agent.report_verification_gate")


def _row(**extra):
    row = {
        "event": "A vs B",
        "provider_event_id": "evt-1",
        "sport": "WNBA",
        "market_type": "spread",
        "selection": "A -1.5",
        "prediction": "Point Spread: A -1.5",
        "spread_line": "-1.5",
        "decimal_price": 1.91,
        "model_probability": 0.57,
        "model_market_edge": 0.047,
        "expected_value_per_unit": 0.089,
        "provider_match_status": "Provider matched",
        "provider_verified": "true",
        "timestamp": "now",
        "book": "Book A",
    }
    row.update(extra)
    return row


def test_current_provider_positive_row_is_verified():
    gate = _gate()
    out = gate.classify_report_row(_row())
    assert out["report_verification_class"] == gate.VERIFIED_BUYER_PICK
    assert out["risk"] == "VERIFIED PRICE"


def test_saved_positive_row_goes_to_watchlist():
    gate = _gate()
    out = gate.classify_report_row(_row(source="uploaded row"))
    assert out["report_verification_class"] == gate.WATCHLIST_VERIFY_PRICE
    rows = gate.build_report_rows([out])
    assert rows[0]["event"] == gate.NO_VERIFIED_MESSAGE


def test_negative_value_row_is_price_rejected():
    gate = _gate()
    out = gate.classify_report_row(_row(model_market_edge=-0.01, expected_value_per_unit=-0.02))
    assert out["report_verification_class"] == gate.NO_PRICE_REJECTED
    assert out["risk"] == "PRICE REJECTED"


def test_missing_line_is_research_only():
    gate = _gate()
    row = _row(prediction="Point Spread: A", spread_line="", line="")
    out = gate.classify_report_row(row)
    assert out["report_verification_class"] == gate.RESEARCH_ONLY


def test_verified_report_does_not_pad_to_100():
    gate = _gate()
    rows = gate.build_report_rows([_row()])
    assert len(rows) == 1
    assert rows[0]["report_verification_class"] == gate.VERIFIED_BUYER_PICK
    assert "Verified count: 1 / 100" in rows[0]["report_renderer_marker"]
