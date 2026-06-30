from __future__ import annotations

from typing import Any, Mapping


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        import pandas as pd  # type: ignore
        if pd.isna(value):
            return ""
    except Exception:
        pass
    text = str(value).strip()
    return "" if text.lower() in {"", "nan", "none", "null", "n/a", "na"} else text


def _row(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return data if isinstance(data, Mapping) else {}
    return getattr(value, "__dict__", {}) or {}


def _first(data: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(data.get(key))
        if value:
            return value
    return ""


def _trim(value: str, limit: int = 42) -> str:
    value = " ".join(str(value or "").split())
    return value if len(value) <= limit else value[: max(0, limit - 1)].rstrip() + "…"


def install(module: Any | None = None) -> Any | None:
    """Make the magazine visibly render canonical-source status.

    This is intentionally presentation-only. It does not invent live data. It
    exposes the provenance already on final_enriched_picks_df rows and turns old
    generic text into explicit status/failure labels.
    """
    if module is None:
        try:
            from . import magazine_book_export as module  # type: ignore
        except Exception:
            return None
    if getattr(module, "_aba_truth_status_patch_v1", False):
        return module

    original_tr = getattr(module, "_tr", lambda value, lang: str(value))
    original_provenance = getattr(module, "api_provenance_lines", lambda row: [])

    def odds_row_label(row: Any) -> str:
        data = _row(row)
        status = _first(data, "odds_status")
        source = _first(data, "odds_source")
        reason = _first(data, "odds_failure_reason")
        if status.upper() == "LIVE":
            return "LIVE_API Odds API"
        if status.upper() in {"UPLOADED_ROW", "FALLBACK", "FALLBACK_CALCULATED"}:
            return "UPLOADED ROW" if status.upper() == "UPLOADED_ROW" else status.upper().replace("_", " ")
        if status:
            return _trim(f"{status}: {reason or source or 'EMPTY_WITH_REASON'}", 44)
        source = _first(data, "odds_source", "data_source")
        return source if source and "cached" not in source.lower() else "EMPTY_WITH_REASON"

    def headline_context_lines(row: Any) -> list[str]:
        data = _row(row)
        context = _first(data, "perplexity_context", "news_summary", "context", "sports_context_summary", "preview_summary", "game_summary")
        bad_tokens = ("context unavailable", "simple news aggregator", "show hn:", "uploaded/cached")
        if context and not any(token in context.lower() for token in bad_tokens):
            return [context]
        reason = _first(data, "context_failure_reason", "perplexity_failure_reason", "news_failure_reason")
        return ["Context unavailable because: " + (reason or "no verified context reached final_enriched_picks_df")]

    def provenance_lines(row: Any) -> list[str]:
        data = _row(row)
        base = list(original_provenance(row) or [])
        status = []
        for label, key in (
            ("Odds", "odds_status"),
            ("SDIO", "sportsdataio_match_status"),
            ("API-FB", "api_football_match_status"),
            ("PPLX", "perplexity_status"),
            ("News", "news_status"),
        ):
            value = _first(data, key)
            if value:
                status.append(f"{label}: {value}")
        if status:
            return [" · ".join(status[:4])] + base[:1]
        return base

    def pairs(row: Any, lang: str) -> list[tuple[str, str]]:
        data = _row(row)
        rows = [
            ("SOURCE", _first(data, "report_source") or "final_enriched_picks_df"),
            ("RUN", _first(data, "report_run_id")[:18] or "current run"),
            ("CACHE", _first(data, "cache_status") or "LIVE_REFRESH"),
            ("ODDS", odds_row_label(data)),
            ("CTX", _first(data, "context_source") or _first(data, "context_status") or "EMPTY_WITH_REASON"),
        ]
        return [(original_tr(label, lang), original_tr(_trim(value, 36), lang)) for label, value in rows if value]

    module._odds_row_label = odds_row_label
    module._headline_context_lines = headline_context_lines
    module.api_provenance_lines = provenance_lines
    module._pairs = pairs
    module._aba_truth_status_patch_v1 = True
    return module
