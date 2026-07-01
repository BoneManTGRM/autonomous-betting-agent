from __future__ import annotations

import re
from typing import Any, Iterable

_PATCH_VERSION = "magazine_report_display_polish_v2_fallback_copy"

SOURCE_LABELS = {
    "Odds API": "Odds",
    "The Odds API": "Odds",
    "SportsDataIO": "SDIO",
    "WeatherAPI": "Weather",
    "API-Football": "API-FB",
    "Perplexity": "PPLX",
    "NewsAPI": "News",
}


def _row(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            data = value.to_dict()
            return dict(data) if isinstance(data, dict) else {}
        except Exception:
            return {}
    return dict(getattr(value, "__dict__", {}) or {})


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _split(value: Any) -> list[str]:
    text = str(value or "").replace("•", "\n").replace(";", "\n").replace("|", "\n")
    return [_clean(part).strip(" -•") for part in text.splitlines() if _clean(part).strip(" -•")]


def _fallback_row(row: Any) -> bool:
    data = _row(row)
    source = _clean(data.get("odds_source") or data.get("data_source")).lower()
    status = _clean(data.get("odds_status")).lower()
    mode = _clean(data.get("risk") or data.get("risk_level") or data.get("risk_label")).lower()
    return any(token in source or token in status or token in mode for token in ("uploaded", "fallback", "cached", "missing"))


def _dedupe(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = _clean(item)
        if text and not text.endswith("."):
            text += "."
        key = text.lower().rstrip(".")
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def _source_label(name: str) -> str:
    return SOURCE_LABELS.get(str(name).strip(), str(name).strip())


def _compact_context_items(sale: Any, data: dict[str, Any], lang: str, limit: int = 2) -> list[str]:
    items: list[str] = []
    for key in (
        "weather_summary",
        "venue_note",
        "weather_location",
        "sports_context_summary",
        "perplexity_context",
        "perplexity_summary",
        "newsapi_summary",
        "news_summary",
    ):
        for item in _split(data.get(key)):
            lowered = item.lower()
            if any(token in lowered for token in ("not returned", "not available", "no live", "fallback report", "odds are not live")):
                continue
            if len(item) > 82:
                item = (item[:81].rsplit(" ", 1)[0] or item[:81]).rstrip(".,;:") + "…"
            items.append(item)
            if len(items) >= limit:
                return sale._wrap(_dedupe(items), lang)
    return []


def _install_renderer_source_labels(module: Any) -> None:
    if getattr(module, "_ABA_SOURCE_LABEL_POLISH_VERSION", "") == _PATCH_VERSION:
        return
    original_api_provenance = getattr(module, "api_provenance", None)
    if not callable(original_api_provenance):
        return

    def polished_api_provenance(row: Any) -> dict[str, list[str]]:
        prov = original_api_provenance(row)
        if _fallback_row(row):
            checked = _dedupe([
                *prov.get("active_sources", []),
                *prov.get("available_no_data_sources", []),
                *prov.get("inactive_sources", []),
            ])
            return {"active_sources": [], "available_no_data_sources": checked, "inactive_sources": []}
        return prov

    def polished_api_provenance_lines(row: Any) -> list[str]:
        prov = polished_api_provenance(row)
        active = [_source_label(name) for name in prov.get("active_sources", [])]
        checked = [_source_label(name) for name in prov.get("available_no_data_sources", [])]
        inactive = [_source_label(name) for name in prov.get("inactive_sources", [])]
        if _fallback_row(row):
            if checked:
                return ["Sources checked: " + " · ".join(checked[:6]) + "; no verified live match."]
            return ["Sources checked: no verified live match."]
        lines: list[str] = []
        if active:
            lines.append("Live sources: " + " · ".join(active))
        if not lines and checked:
            lines.append("Sources checked: " + " · ".join(checked))
        if not lines and inactive:
            lines.append("Sources configured: " + " · ".join(inactive))
        return lines

    def polished_active_note(row: Any) -> str:
        lines = polished_api_provenance_lines(row)
        return lines[0] + ("" if lines[0].endswith(".") else ".") if lines else "Sources checked: none."

    module.api_provenance = polished_api_provenance
    module.api_provenance_lines = polished_api_provenance_lines
    module._active_note = polished_active_note
    module._ABA_SOURCE_LABEL_POLISH_VERSION = _PATCH_VERSION


def install_sale_ready_polish() -> None:
    try:
        from autonomous_betting_agent import magazine_sale_ready_patch as sale
    except Exception:
        return

    if getattr(sale, "_ABA_DISPLAY_POLISH_VERSION", "") == _PATCH_VERSION:
        return

    def polished_team_items(row: Any, side: str = "") -> list[str]:
        lang = sale._impl._lang(row)
        data = sale._row(row)
        keys = (
            f"{side}_team_form",
            f"{side}_team_record",
            f"{side}_recent_results",
            "team_snapshot_home",
            "team_snapshot_away",
            "team_stats_summary",
            "recent_results",
            "perplexity_context",
        )
        items = sale._source_items(data, keys, 3, 62)
        if items:
            return sale._wrap(_dedupe(items)[:3], lang)
        if _fallback_row(data):
            return sale._wrap([
                "Live team feed not linked to this row.",
                "Use as watchlist until provider match is verified.",
            ], lang)
        return sale._wrap(["Team context was not returned.", "Check lineup/news before entry."], lang)

    def polished_injury_items(row: Any, prefix: str = "") -> list[str]:
        lang = sale._impl._lang(row)
        data = sale._row(row)
        keys = (
            f"{prefix}_injuries",
            f"{prefix}_injury_report",
            f"{prefix}_lineup_status",
            f"{prefix}_player_notes",
            "injury_report",
            "injuries",
            "lineup_status",
            "key_players",
            "perplexity_context",
        )
        items = sale._source_items(data, keys, 2, 66)
        if items:
            return sale._wrap(_dedupe(items)[:2], lang)
        if _fallback_row(data):
            return sale._wrap([
                "Lineup/injury feed not verified for this row.",
                "Check team news before entry.",
            ], lang)
        return sale._wrap(["Lineup/injury context was not returned.", "Verify before entry."], lang)

    def polished_matchup_items(row: Any) -> list[str]:
        lang = sale._impl._lang(row)
        data = sale._row(row)
        if _fallback_row(data):
            items = ["Watchlist only: current price and live context need verification."]
            items.extend(_compact_context_items(sale, data, lang, 2))
            return sale._wrap(_dedupe(items)[:3], lang)
        items: list[str] = []
        keys = (
            "perplexity_context",
            "perplexity_summary",
            "sports_context_summary",
            "preview_summary",
            "game_summary",
            "short_reason",
            "matchup_note",
        )
        for item in sale._source_items(data, keys, 1, 82):
            if "odds are not live" not in item.lower():
                items.append(item)
        try:
            items.extend(sale._compact_weather(str(data.get("weather_summary", "") or ""), lang)[:1])
        except Exception:
            pass
        if not items:
            items.append("Pregame context was not returned; verify odds and news before entry.")
        return sale._wrap(_dedupe(items)[:3], lang)

    def polished_risk_items(row: Any) -> list[str]:
        lang = sale._impl._lang(row)
        data = sale._row(row)
        if _fallback_row(data):
            return sale._wrap([
                "Fallback/watchlist only.",
                "Confirm current price before entry.",
                "Re-run live APIs before official use.",
            ], lang)
        return sale.sale_ready_risk_items(row)

    def polished_chain_items(row: Any) -> list[str]:
        lang = sale._impl._lang(row)
        data = sale._row(row)
        explicit: list[str] = []
        for key in ("chain_notes", "main_read", "add_on_legs", "parlay_notes", "live_betting_notes", "flash_market_notes", "prop_market_notes"):
            explicit.extend(_split(data.get(key)))
        if explicit and not _fallback_row(data):
            return sale._wrap(_dedupe(explicit)[:3], lang)
        if _fallback_row(data):
            return sale._wrap([
                "Straight watchlist only.",
                "Do not parlay fallback rows.",
                "Wait for verified odds and compatible legs.",
            ], lang)
        return sale.sale_ready_chain_items(row)

    def install_renderer(module: Any) -> Any:
        if module is None:
            return module
        try:
            module._team_items = polished_team_items
            module.team_items = polished_team_items
            module._injury_items = polished_injury_items
            module.injury_items = polished_injury_items
            module._matchup_items = polished_matchup_items
            module.matchup_items = polished_matchup_items
            module._risk_items = polished_risk_items
            module.risk_items = polished_risk_items
            module._chain_items = polished_chain_items
            module.chain_items = polished_chain_items
            _install_renderer_source_labels(module)
        except Exception:
            pass
        return module

    original_apply = getattr(sale, "apply_magazine_sale_ready_patch", None)
    if callable(original_apply) and getattr(original_apply, "_ABA_DISPLAY_POLISH_VERSION", "") != _PATCH_VERSION:
        def wrapped_apply(module: Any) -> Any:
            return install_renderer(original_apply(module))

        wrapped_apply._ABA_DISPLAY_POLISH_VERSION = _PATCH_VERSION
        sale.apply_magazine_sale_ready_patch = wrapped_apply

    sale.sale_ready_team_items = polished_team_items
    sale.sale_ready_injury_items = polished_injury_items
    sale.sale_ready_matchup_items = polished_matchup_items
    sale.sale_ready_risk_items = polished_risk_items
    sale.sale_ready_chain_items = polished_chain_items
    sale._ABA_DISPLAY_POLISH_VERSION = _PATCH_VERSION

    try:
        import autonomous_betting_agent.magazine_book_export as renderer
        install_renderer(renderer)
    except Exception:
        pass


def install() -> None:
    install_sale_ready_polish()


install()
