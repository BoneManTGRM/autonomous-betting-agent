"""Stress-test full-pick magazine rendering for long text.

The goal is a global guard: future report pages should shrink, wrap, or use
compact labels instead of drawing variable text outside its assigned region.
"""

From __future__ import annotations

From pathlib import Path

from autonomous_betting_agent import magazine_book_export as magazine
from autonomous_betting_agent.report_image_export_service import PNG_HEADER


Def _row(**extra: str) -> dict[str, str]:
    row = {
        "event_name": "Alpha at Beta",
        "away_team": "Alpha",
        "home_team": "Beta",
        "sport": "FIFA WORLD CUP",
        "season_label": "FIFA WORLD CUP REGULAR SEASON",
        "market_type": "GAME TOTAL",
        "pick": "OVER 2.5",
        "american_odds": "+115",
        "model_probability": "0.63",
        "model_market_edge": "0.071",
        "expected_value": "0.084",
        "recommended_stake_units": "1.0",
        "risk": "THIN EDGE FAVORITE",
        "final_decision": "PLAY STANDARD",
        "preview_summary": "Market and model evidence support this read.",
        "away_record": "3-1-1",
        "home_record": "4-0-1",
        "away_last_10": "6W-2D-2L",
        "home_last_10": "7W-2D-1L",
        "away_form": "Strong recent form with stable pressure metrics.",
        "home_form": "Stable possession profile with positive finishing trend.",
        "matchup_notes": "Venue and market movement should be confirmed before publishing.",
        "final_explanation": "Use only if the line remains playable and key news does not change.",
    }
    row.update(extra)
    return row


CASES = [
    (
        "iraq_france_es",
        "es",
        _row(event_name="Iraq it France", away_team="Iraq", home_team="France"),
    ),
    (
        "boxing_es",
        "es",
        _row(
            sport="BOXING",
            season_label="BOXING REGULAR SEASON",
            event_name="Liam Paro vs Lewis Crocker",
            away_team="Liam Paro",
            home_team="Lewis Crocker",
            market_type="MONEYLINE",
            pick="LEWIS CROCKER MONEYLINE",
            risk="FAVORITO DE VENTAJA DELGADA",
        ),
    ),
    (
        "bosnia_es",
        "es",
        _row(
            event_name="Qatar vs Bosnia & Herzegovina",
            away_team="Qatar",
            home_team="Bosnia & Herzegovina",
            pick="BOSNIA & HERZEGOVINA MONEYLINE",
            risk="RESEARCH ONLY",
        ),
    ),
    (
        "netherlands_es",
        "es",
        _row(
            event_name="Netherlands at Tunisia",
            away_team="Netherlands",
            home_team="Tunisia",
            pick="UNDER 3.5",
            risk="WATCHLIST ONLY",
        ),
    ),
    (
        "synthetic_extreme_en",
        "en",
        _row(
            event_name="Extremely Long International Team Name With Extra Words vs Ultra Long Opponent Name The Third",
            away_team="Extremely Long International Team Name With Extra Words",
            home_team="Ultra Long Opponent Name The Third",
            season_label="International Experimental Tournament Regular Season With Extra Long Stage Label",
            market_type="Extremely Long Market Name That Must Stay Inside",
            pick="Extremely Long Pick Text That Must Stay Inside",
            risk="Very Long Custom Research Label That Must Stay Inside",
        ),
    ),
]


def _assert_public_contract() -> None:
    assert magazine.MAGAZINE_STYLE_VERSION == "premium_v4_reference_compact"
    assert magazine.TEAM_DATA_FALLBACK == "Data not available from uploaded row"
    assert magazine.PLAYER_DATA_FALLBACK == "Player data not available in uploaded row"
    for name in (
        "render_full_pick_magazine_page",
        "render_full_pick_magazine_page_png",
        "render_full_magazine_book_pages",
        "render_full_magazine_book_png",
        "render_full_magazine_book_pdf",
        "render_full_magazine_zip",
        "pick_full_page_filename",
        "sanitize_image_filename",
    ):
        assert hasattr(magazine, name), f"Missing public function: {name}"
    assert hasattr(magazine, "validate_magazine_layout_no_overflow")


def main() -> None:
    _assert_public_contract()
    out_dir = Path("diagnostics")
    out_dir.mkdir(exist_ok=True)
    for case_name, language, row in CASES:
        warnings = magazine.validate_magazine_layout_no_overflow(row, language=language)
        assert not warnings, f"case_{case_name}: {warnings}"
        image = magazine.render_full_pick_magazine_page(
            row,
            report_name="Autofit Stress",
            page_number=1,
            total_pages=1,
            use_team_logo=False,
            language=language,
        )
        png = magazine.render_full_pick_magazine_page_png(
            row,
            report_name="Autofit Stress",
            page_number=1,
            total_pages=1,
            use_team_logo=False,
            language=language,
        )
        assert image.size == (magazine.PAGE_WIDTH, magazine.PAGE_HEIGHT)
        assert png.startswith(PNG_HEADER)
        assert len(png) > 10_000, f"{case_name}: PNG too small"
        (out_dir / f"magazine_autofit_{case_name}.png").write_bytes(png)
    print(f"magazine autofit stress passed: {len(CASES)} cases")


if __name__ == "__main__":
    main()
