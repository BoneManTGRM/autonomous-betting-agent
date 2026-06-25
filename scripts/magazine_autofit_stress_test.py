from __future__ import annotations

from autonomous_betting_agent import magazine_book_export as magazine
from autonomous_betting_agent.report_image_export_service import PNG_HEADER


def main() -> None:
    rows = [
        {"event_name": "Iraq at France", "away_team": "Iraq", "home_team": "France", "sport": "FIFA WORLD CUP", "market_type": "GAME TOTAL", "pick": "OVER 2.5", "risk": "THIN EDGE FAVORITE"},
        {"event_name": "Liam Paro vs Lewis Crocker", "away_team": "Liam Paro", "home_team": "Lewis Crocker", "sport": "BOXING", "market_type": "MONEYLINE", "pick": "LEWIS CROCKER MONEYLINE", "risk": "FAVORITO DE VENTAJA DELGADA"},
        {"event_name": "Qatar vs Bosnia & Herzegovina", "away_team": "Qatar", "home_team": "Bosnia & Herzegovina", "sport": "FIFA WORLD CUP", "market_type": "MONEYLINE", "pick": "BOSNIA & HERZEGOVINA MONEYLINE", "risk": "RESEARCH ONLY"},
        {"event_name": "Netherlands at Tunisia", "away_team": "Netherlands", "home_team": "Tunisia", "sport": "FIFA WORLD CUP", "market_type": "GAME TOTAL", "pick": "UNDER 3.5", "risk": "WATCHLIST ONLY"},
    ]
    assert hasattr(magazine, "validate_magazine_layout_no_overflow")
    for row in rows:
        language = "es"
        warnings = magazine.validate_magazine_layout_no_overflow(row, language=language)
        assert not warnings, warnings
        png = magazine.render_full_pick_magazine_page_png(row, use_team_logo=False, language=language)
        assert png.startswith(PNG_HEADER)
        assert len(png) > 10000
    print("magazine autofit check passed")


if __name__ == "__main__":
    main()
