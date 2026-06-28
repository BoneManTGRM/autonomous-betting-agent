from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pandas as pd

import autonomous_betting_agent.ui_i18n_phase3e  # noqa: F401
from autonomous_betting_agent.dynamic_odds_display import build_dynamic_odds_shadow_rows
from autonomous_betting_agent.odds_value_engine import (
    BLOCKED_INVALID_PROBABILITY,
    BLOCKED_MISSING_ODDS,
    BLOCKED_STALE_LINE,
    PLAYABLE_PLUS_EV,
    PREDICTION_ONLY_NOT_PLUS_EV,
    WATCHLIST_VALUE,
    advisory_odds_value_summary,
    build_advisory_odds_value_rows,
)
from autonomous_betting_agent.ui_i18n import localize_dataframe

NOW = datetime(2026, 6, 28, 20, 0, 0, tzinfo=timezone.utc)


def row(selection: str, odds: float | None, probability: float = 0.55, *, book: str = "BookA", market: str = "h2h", quality: str = "STRONG SAMPLE", loaded: bool = True) -> dict[str, object]:
    data: dict[str, object] = {
        "event": "Team A at Team B",
        "prediction": selection,
        "market_type": market,
        "bookmaker": book,
        "model_probability": probability,
        "odds_last_update": "2026-06-28T19:50:00Z",
        "event_start_utc": "2026-06-28T22:00:00Z",
        "model_market_edge": 0.12,
        "expected_value_per_unit": 0.10,
        "lock_ready": True,
        "publish_ready": True,
        "proof_hash": "phase3e5-proof",
        "model_quality_label": quality,
        "lr_model_loaded": loaded,
    }
    if odds is not None:
        data["decimal_price"] = odds
    return data


def market_rows() -> list[dict[str, object]]:
    return [row("Team A", 2.20, 0.55), row("Team B", 1.85, 0.45)]


def test_core_advisory_formulas() -> None:
    valued = build_advisory_odds_value_rows(market_rows(), now=NOW)
    first = valued[0]
    raw = 1 / 2.20
    total = 1 / 2.20 + 1 / 1.85
    no_vig = raw / total
    assert first["advisory_raw_implied_probability"] == round(raw, 6)
    assert first["advisory_market_hold"] == round(total - 1, 6)
    assert first["advisory_no_vig_implied_probability"] == round(no_vig, 6)
    assert first["advisory_raw_edge"] == round(0.55 - raw, 6)
    assert first["advisory_no_vig_edge"] == round(0.55 - no_vig, 6)
    assert first["advisory_raw_EV"] == round(0.55 * 2.20 - 1, 6)
    assert first["advisory_fair_odds"] == round(1 / 0.55, 6)
    assert first["advisory_target_odds"] == round(1 / 0.55 + 0.03, 6)
    assert first["advisory_no_vig_value_ratio"] == round(0.55 / no_vig - 1, 6)


def test_line_shopping_and_no_vig_are_sportsbook_specific() -> None:
    rows = market_rows() + [row("Team A", 2.50, 0.55, book="BookB")]
    valued = build_advisory_odds_value_rows(rows, now=NOW)
    book_a = next(item for item in valued if item["prediction"] == "Team A" and item["bookmaker"] == "BookA")
    book_b = next(item for item in valued if item["prediction"] == "Team A" and item["bookmaker"] == "BookB")
    assert book_a["advisory_best_available_decimal_odds"] == 2.5
    assert book_a["advisory_best_available_sportsbook"] == "BookB"
    assert book_a["advisory_best_price_EV"] == round(0.55 * 2.5 - 1, 6)
    assert book_b["advisory_no_vig_implied_probability"] is None
    assert book_b["advisory_market_completeness_status"] == "INCOMPLETE_MARKET"


def test_missing_invalid_and_stale_inputs_fail_safely() -> None:
    missing_odds = build_advisory_odds_value_rows([row("Team A", None, 0.55)], now=NOW)[0]
    assert missing_odds["advisory_playable_status"] == BLOCKED_MISSING_ODDS
    invalid_probability = build_advisory_odds_value_rows([row("Team A", 2.0, 120)], now=NOW)[0]
    assert invalid_probability["advisory_playable_status"] == BLOCKED_INVALID_PROBABILITY
    stale_source = row("Team A", 2.2, 0.55)
    stale_source["odds_last_update"] = "2026-06-28T19:00:00Z"
    stale = build_advisory_odds_value_rows([stale_source], now=NOW)[0]
    assert stale["advisory_stale_line_status"] == "STALE"
    assert stale["advisory_playable_status"] == BLOCKED_STALE_LINE


def test_playable_watchlist_prediction_only_and_duplicate_labels() -> None:
    prediction_only = build_advisory_odds_value_rows([row("Team A", 1.35, 0.74)], now=NOW)[0]
    assert prediction_only["advisory_playable_status"] == PREDICTION_ONLY_NOT_PLUS_EV
    watchlist = build_advisory_odds_value_rows([
        row("Team A", 2.25, 0.55, quality="DATA BLOCKED", loaded=False),
        row("Team B", 1.85, 0.45, quality="DATA BLOCKED", loaded=False),
    ], now=NOW)[0]
    assert watchlist["advisory_playable_status"] == WATCHLIST_VALUE
    playable = build_advisory_odds_value_rows([row("Team A", 2.35, 0.58), row("Team B", 1.70, 0.42)], now=NOW)[0]
    assert playable["advisory_playable_status"] == PLAYABLE_PLUS_EV
    duplicates = build_advisory_odds_value_rows([
        row("Team A", 2.35, 0.58),
        row("Team B", 1.70, 0.42),
        row("Team A -1", 2.20, 0.57, market="spread"),
        row("Team B +1", 1.80, 0.43, market="spread"),
    ], now=NOW)
    assert len([item for item in duplicates if item["advisory_playable_status"] == PLAYABLE_PLUS_EV]) == 1
    assert len(duplicates) == 4


def test_advisory_fields_do_not_overwrite_official_fields_and_are_deterministic() -> None:
    source = market_rows()
    before = deepcopy(source)
    first = build_advisory_odds_value_rows(source, now=NOW)
    second = build_advisory_odds_value_rows(source, now=NOW)
    assert source == before
    assert first == second
    assert first[0]["model_probability"] == before[0]["model_probability"]
    assert first[0]["model_market_edge"] == before[0]["model_market_edge"]
    assert first[0]["expected_value_per_unit"] == before[0]["expected_value_per_unit"]
    assert first[0]["lock_ready"] is True
    assert first[0]["publish_ready"] is True
    assert "raw_EV" not in first[0]
    assert "playable_status" not in first[0]


def test_dynamic_display_summary_and_spanish_labels() -> None:
    shadow_rows = build_dynamic_odds_shadow_rows(market_rows())
    assert shadow_rows[0]["advisory_odds_math_mode"] == "ADVISORY_ONLY"
    summary = advisory_odds_value_summary(shadow_rows)
    assert summary["live_application"] == "OFF"
    assert summary["applied_live_count"] == 0
    localized = localize_dataframe(pd.DataFrame(shadow_rows), "es")
    assert any("advisory" in column.lower() or "asesor" in column.lower() for column in localized.columns)
