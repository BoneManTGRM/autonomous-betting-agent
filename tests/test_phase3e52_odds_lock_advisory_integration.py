from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path

import pandas as pd

import autonomous_betting_agent.advisory_i18n_phase3e5  # noqa: F401
from autonomous_betting_agent.advisory_odds_value_display import (
    advisory_csv_frame,
    advisory_frame,
    advisory_report_text,
    proof_safety_comparison,
    validate_advisory_rows,
)
from autonomous_betting_agent.ui_i18n import localize_dataframe

ODDS_LOCK_PATH = Path("pages/odds_lock_pro.py")


def real_file_fixture() -> list[dict[str, object]]:
    return [
        {
            "event": "Team A at Team B",
            "prediction": "Team A",
            "sport": "basketball",
            "league": "test league",
            "market_type": "h2h",
            "bookmaker": "BookA",
            "decimal_price": 2.35,
            "model_probability": 0.58,
            "expected_value_per_unit": 0.10,
            "model_market_edge": 0.12,
            "lock_ready": True,
            "official_lock_ready": False,
            "publish_ready": True,
            "proof_hash": "hash-a",
            "proof_id": "proof-a",
            "locked_at_utc": "2026-06-28T18:00:00Z",
            "result_status": "pending",
            "odds_last_update": "2026-06-28T19:50:00Z",
            "event_start_utc": "2026-06-28T22:00:00Z",
            "model_quality_label": "STRONG SAMPLE",
            "lr_model_loaded": True,
        },
        {
            "event": "Team A at Team B",
            "prediction": "Team B",
            "sport": "basketball",
            "league": "test league",
            "market_type": "h2h",
            "bookmaker": "BookA",
            "decimal_price": 1.70,
            "model_probability": 0.42,
            "expected_value_per_unit": -0.01,
            "model_market_edge": -0.02,
            "lock_ready": False,
            "official_lock_ready": False,
            "publish_ready": False,
            "proof_hash": "hash-b",
            "proof_id": "proof-b",
            "locked_at_utc": "2026-06-28T18:01:00Z",
            "result_status": "pending",
            "odds_last_update": "2026-06-28T19:50:00Z",
            "event_start_utc": "2026-06-28T22:00:00Z",
            "model_quality_label": "STRONG SAMPLE",
            "lr_model_loaded": True,
        },
    ]


def odds_lock_source() -> str:
    return ODDS_LOCK_PATH.read_text(encoding="utf-8")


def helper_source() -> str:
    tree = ast.parse(odds_lock_source())
    lines = odds_lock_source().splitlines()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "show_advisory_odds_value_panel":
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError("show_advisory_odds_value_panel not found")


def test_odds_lock_pro_static_integration_exists() -> None:
    source = odds_lock_source()
    ast.parse(source)
    assert "import autonomous_betting_agent.advisory_i18n_phase3e5" in source
    assert "from autonomous_betting_agent.advisory_odds_value_display import" in source
    assert "show_advisory_odds_value_panel" in source
    assert "t('advisory_odds_value')" in source
    assert "tabs[7]" in source


def test_helper_uses_advisory_helpers_without_formula_duplication_or_lock_calls() -> None:
    body = helper_source()
    required_helpers = [
        "advisory_frame(",
        "advisory_summary_counts(",
        "playable_table(",
        "watchlist_table(",
        "prediction_only_table(",
        "blocked_reason_summary(",
        "sportsbook_hold_summary(",
        "line_shopping_summary(",
        "stale_line_summary(",
        "duplicate_conflict_summary(",
        "validate_advisory_rows(",
        "advisory_csv_frame(",
        "advisory_report_text(",
    ]
    for helper in required_helpers:
        assert helper in body
    forbidden_tokens = [
        "lock_rows(",
        "research_lock_rows(",
        "publish_locked_rows(",
        "save_persistent_ledger(",
        "save_held_rows(",
        "st.session_state",
        "lock_ready =",
        "official_lock_ready =",
        "publish_ready =",
        "official_ev_pick =",
        "raw_EV =",
        "no_vig_edge =",
        "1 / decimal",
        "model_probability *",
    ]
    for token in forbidden_tokens:
        assert token not in body


def test_advisory_display_copy_does_not_mutate_real_file_fixture_fields() -> None:
    source = real_file_fixture()
    before = deepcopy(source)
    advisory = advisory_frame(pd.DataFrame(source))
    assert source == before
    assert len(advisory) == len(source)
    comparison = proof_safety_comparison(source, advisory)
    assert comparison["passed"] is True
    validation = validate_advisory_rows(pd.DataFrame(source))
    assert validation["proof_safety_check_result"]["passed"] is True
    for original, output in zip(before, advisory.to_dict("records")):
        for field in [
            "lock_ready",
            "official_lock_ready",
            "publish_ready",
            "model_probability",
            "expected_value_per_unit",
            "model_market_edge",
            "proof_hash",
            "proof_id",
            "locked_at_utc",
            "result_status",
        ]:
            assert output[field] == original[field]


def test_advisory_csv_and_report_remain_advisory_only() -> None:
    source = real_file_fixture()
    advisory = advisory_frame(source)
    csv = advisory_csv_frame(advisory)
    assert len(csv) == len(source)
    assert any(column.startswith("advisory_") for column in csv.columns)
    assert "official_ev_pick" not in csv.columns
    report = advisory_report_text(advisory)
    assert "No bets were placed" in report
    assert "Live application remains OFF" in report


def test_spanish_advisory_labels_still_resolve() -> None:
    frame = pd.DataFrame([{"advisory_playable_status": "PLAYABLE_PLUS_EV", "advisory_raw_EV": 0.12}])
    localized = localize_dataframe(frame, "es")
    assert any("asesor" in column.lower() for column in localized.columns)
    assert localized.iloc[0, 0] in {"JUGABLE +EV", "PLAYABLE_PLUS_EV"}
