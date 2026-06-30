from __future__ import annotations

from typing import Any, Mapping

_PATCH_VERSION = "magazine_pregame_truth_gate_v1"

POSTGAME_RESULT_TOKENS = (
    " ended ",
    " defeated ",
    " beat ",
    " won ",
    " lost ",
    " victory ",
    " final score",
    " confirmed ",
    " confirming ",
    " goals from ",
    " goal from ",
    " match was won",
)


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return dict(data) if isinstance(data, Mapping) else {}
    return dict(getattr(value, "__dict__", {}) or {})


def _clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\n", " ").split()).strip()


def _is_postgame_text(value: Any) -> bool:
    text = f" {_clean(value).lower()} "
    return any(token in text for token in POSTGAME_RESULT_TOKENS)


def _is_live_odds(row_like: Any) -> bool:
    row = _row(row_like)
    status = _clean(row.get("odds_status")).lower()
    source = _clean(row.get("odds_source") or row.get("data_source")).lower()
    if any(token in source for token in ("uploaded", "fallback", "cached", "missing")):
        return False
    if source in {"live_api", "odds api", "the odds api", "live_source"}:
        return True
    return status in {"live", "live_api"} and not source


def install() -> None:
    try:
        from autonomous_betting_agent import magazine_live_api_enrichment as live
    except Exception:
        return
    if getattr(live, "_ABA_PREGAME_TRUTH_PATCH", "") == _PATCH_VERSION:
        return

    original_bad_context = getattr(live, "_bad_context", None)
    original_render_cleanup = getattr(live, "_render_cleanup", None)

    def bad_context(value: Any, row: Mapping[str, Any]) -> bool:
        if _is_postgame_text(value):
            return True
        if callable(original_bad_context):
            return bool(original_bad_context(value, row))
        return not bool(_clean(value))

    def render_cleanup(row_like: Any) -> dict[str, Any]:
        row = original_render_cleanup(row_like) if callable(original_render_cleanup) else _row(row_like)
        for key in ("perplexity_context", "perplexity_summary", "newsapi_summary", "news_summary", "sports_context_summary", "preview_summary", "game_summary", "short_reason", "matchup_note", "matchup_notes"):
            if _is_postgame_text(row.get(key)):
                row[key] = ""
        if not _is_live_odds(row):
            row["odds_status"] = "UPLOADED_ROW" if (row.get("decimal_odds") or row.get("american_odds") or row.get("odds")) else "MISSING"
            row["odds_source"] = "UPLOADED_ROW" if row["odds_status"] == "UPLOADED_ROW" else "MISSING"
            row["risk"] = "FALLBACK MODE"
            row["risk_level"] = "FALLBACK MODE"
            row["risk_label"] = "FALLBACK MODE"
            row["final_decision"] = "WATCHLIST"
            row["why_lose"] = "Fallback data used.\nVerify live odds before entry.\nDo not use until the price is confirmed."
            row["risk_notes"] = row["why_lose"]
        return row

    live._bad_context = bad_context
    live._is_live_odds = _is_live_odds
    live._render_cleanup = render_cleanup
    live._ABA_PREGAME_TRUTH_PATCH = _PATCH_VERSION
    try:
        live.ENRICHMENT_VERSION = str(live.ENRICHMENT_VERSION) + "_pregame_truth_v1"
    except Exception:
        pass


install()
