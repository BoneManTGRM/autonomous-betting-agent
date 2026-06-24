"""Local sport and market support rules.

The helpers in this module do not delete rows. They add review/exclude flags so
operators can decide whether a row should remain research-only or be promoted.
"""

from __future__ import annotations

from typing import Any, Mapping

SUPPORTED_SPORTS = {
    "soccer",
    "football",
    "basketball",
    "nba",
    "wnba",
    "nfl",
    "nhl",
    "mlb",
    "mma",
    "ufc",
    "boxing",
    "cfl",
    "rugby",
    "cricket",
}

SUPPORTED_MARKETS = {
    "moneyline",
    "h2h",
    "winner",
    "spread",
    "handicap",
    "total",
    "totals",
    "over_under",
    "ou",
}

TENNIS_TERMS = {"tennis", "atp", "wta", "itf", "challenger"}


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def normalize_sport(value: Any) -> str:
    return _text(value).lower().replace("_", " ").replace("-", " ")


def normalize_market(value: Any) -> str:
    return _text(value).lower().replace(" ", "_").replace("-", "_")


def _row_sport(row: Mapping[str, Any]) -> str:
    return normalize_sport(row.get("sport") or row.get("sport_key") or row.get("league") or row.get("competition"))


def _row_market(row: Mapping[str, Any]) -> str:
    return normalize_market(row.get("market") or row.get("market_type") or row.get("bet_type"))


def _contains_any(value: str, terms: set[str]) -> bool:
    return any(term in value for term in terms)


def market_support_status(row: Mapping[str, Any], tennis_mode: str = "review") -> dict[str, Any]:
    """Return support status and review reasons for a row.

    Status values:
    - supported: sport and market are explicit supported matches.
    - review: row should remain review/research until verified.
    - blocked: row should not be promoted under current operator settings.
    """
    sport = _row_sport(row)
    market = _row_market(row)
    tennis_mode = _text(tennis_mode).lower() or "review"
    reasons: list[str] = []
    status = "supported"

    if not sport:
        status = "review"
        reasons.append("Sport is missing.")
    elif _contains_any(sport, TENNIS_TERMS):
        if tennis_mode == "block":
            status = "blocked"
            reasons.append("Tennis-style rows are blocked by the current local setting.")
        else:
            status = "review"
            reasons.append("Tennis-style rows default to review mode before official promotion.")
    elif not _contains_any(sport, SUPPORTED_SPORTS):
        status = "review"
        reasons.append("Sport is not in the explicit supported list.")

    if not market:
        if status != "blocked":
            status = "review"
        reasons.append("Market type is missing.")
    elif not (market in SUPPORTED_MARKETS or _contains_any(market, SUPPORTED_MARKETS)):
        if status != "blocked":
            status = "review"
        reasons.append("Market type is not in the explicit supported list.")

    grading_hint = "Use row-level and event-level grading rules; confirm push/cancel/draw handling before public proof."
    odds_hint = "Use proof-safe consensus/average price when available; review outlier prices before promotion."
    push_cancel_hint = "Apply sport/market-specific push, void, cancellation, and draw rules before training memory."

    return {
        "market_support_status": status,
        "market_support_reasons": reasons,
        "sport_normalized": sport,
        "market_normalized": market,
        "sport_grading_hint": grading_hint,
        "sport_odds_hint": odds_hint,
        "market_push_cancel_hint": push_cancel_hint,
    }


def apply_market_support_flags(row: Mapping[str, Any], tennis_mode: str = "review") -> dict[str, Any]:
    payload = dict(row)
    status = market_support_status(payload, tennis_mode=tennis_mode)
    payload.update(status)
    if status["market_support_status"] == "blocked":
        payload["ledger_type"] = "quarantine"
    elif status["market_support_status"] == "review":
        payload.setdefault("ledger_type", "research")
    return payload


def is_market_supported(row: Mapping[str, Any], tennis_mode: str = "review") -> bool:
    return market_support_status(row, tennis_mode=tennis_mode)["market_support_status"] == "supported"


def market_review_reasons(row: Mapping[str, Any], tennis_mode: str = "review") -> list[str]:
    return list(market_support_status(row, tennis_mode=tennis_mode)["market_support_reasons"])
