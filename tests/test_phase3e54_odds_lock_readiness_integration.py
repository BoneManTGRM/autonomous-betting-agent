from __future__ import annotations

import ast
from pathlib import Path

ODDS_LOCK_PATH = Path("pages/odds_lock_pro.py")


def odds_lock_source() -> str:
    return ODDS_LOCK_PATH.read_text(encoding="utf-8")


def helper_source() -> str:
    source = odds_lock_source()
    tree = ast.parse(source)
    lines = source.splitlines()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "show_advisory_odds_value_panel":
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError("show_advisory_odds_value_panel not found")


def test_odds_lock_imports_fresh_slate_readiness_checker() -> None:
    source = odds_lock_source()
    ast.parse(source)
    assert "fresh_slate_readiness_check" in source
    assert "from autonomous_betting_agent.advisory_odds_value_display import" in source


def test_odds_lock_advisory_panel_renders_readiness_before_tables() -> None:
    body = helper_source()
    readiness_position = body.index("fresh_slate_readiness_check(advisory)")
    playable_table_position = body.index("playable_table(advisory)")
    assert readiness_position < playable_table_position
    assert "Fresh Slate Readiness" in odds_lock_source()
    assert "readiness_score" in body
    assert "readiness_status" in body
    assert "recommended_next_action" in body


def test_odds_lock_readiness_integration_does_not_control_official_lock_logic() -> None:
    body = helper_source()
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
        "promotion_eligible =",
        "stake_units =",
    ]
    for token in forbidden_tokens:
        assert token not in body


def test_odds_lock_readiness_integration_keeps_existing_advisory_tables() -> None:
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
