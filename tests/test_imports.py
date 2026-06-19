from pathlib import Path

from autonomous_betting_agent import live_odds
from autonomous_betting_agent import pick_hold_store


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_store_helpers_import():
    assert callable(pick_hold_store.save_held_rows)
    assert callable(pick_hold_store.load_held_rows)
    assert callable(pick_hold_store.verify_held_rows)
    assert callable(pick_hold_store.store_snapshot)


def test_live_odds_models_import():
    assert hasattr(live_odds, "OutcomePrice")
    assert hasattr(live_odds, "MarketLine")
    assert hasattr(live_odds, "scan_market")


def test_pro_predictor_handoff_source_contains_persistence_and_market_type():
    source = (REPO_ROOT / "pages" / "pro_predictor.py").read_text(encoding="utf-8")
    assert "persist_handoff" in source
    assert "save_held_rows('pro_predictor_latest_rows'" in source
    assert "market_type = getattr(outcome, 'market', 'h2h')" in source
    assert "line_point" in source
