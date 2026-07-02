from __future__ import annotations

from typing import Any, Iterable
import re

from autonomous_betting_agent.report_public_quality import (
    build_full_market_label,
    is_saved_source,
    public_action_label,
    public_recommendation_status,
    public_source_warning,
    sanitize_public_text,
    trim_complete_sentence,
)

VERSION = "active_magazine_export_guard_v1"
NO_PLAY = "NO " + "BET / PRICE REJECTED"
_DANGLING = ("where", "with", "with the", "who are", "because", "and", "or", "the", "in", "at", "for", "meaning")
_NOTE_KEYS = ("weather_summary", "venue_weather", "weather_risk", "weather_location", "expanded_matchup_context", "sports_context_summary", "preview_summary", "game_summary", "matchup_note", "matchup_notes", "news_summary", "newsapi_summary", "perplexity_summary", "perplexity_context", "sportsdataio_context", "api_football_summary", "line_movement_summary", "line_movement", "price_movement")


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("−", "-").replace("–", "-").replace("—", "-").strip())


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


def _first(data: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        text = _clean(data.get(key))
        if text and text.lower() not in {"nan", "none", "null", "n/a", "na", "--", "data unavailable", "not provided"}:
            return text
    return default


def _num(data: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        raw = _first(data, key, default="")
        if not raw:
            continue
        try:
            return float(raw.replace("%", "").replace(",", ""))
        except Exception:
            continue
    return None


def _family(data: dict[str, Any]) -> str:
    text = " ".join(_clean(data.get(k)).lower().replace("_", " ") for k in ("market_type", "market", "market_name", "wager_type", "prediction", "pick", "selection"))
    if any(token in text for token in ("total", "over", "under")):
        return "total"
    if "run line" in text or "puck line" in text:
        return "run_line"
    if any(token in text for token in ("spread", "handicap", "point spread")):
        return "spread"
    if any(token in text for token in ("moneyline", "winner", "h2h")):
        return "moneyline"
    return "pick"


def _line(data: dict[str, Any]) -> str:
    raw = _first(data, "total_line", "game_total_line", "spread_line", "run_line", "line_point", "line", "point", "points", "handicap", "threshold", "line_value", "market_line", "line_display", default="")
    if raw:
        try:
            num = float(raw.replace("+", "").replace(",", ""))
            return f"+{num:g}" if num > 0 and _family(data) != "total" else f"{num:g}"
        except Exception:
            return raw
    blob = " | ".join(_clean(data.get(k)) for k in ("prediction", "pick", "display_pick", "exact_bet", "matchup_note", "matchup_notes", "sports_context_summary") if _clean(data.get(k)))
    if _family(data) == "total":
        match = re.search(r"\b(?:over|under|total|set at)\D{0,36}(\d+(?:\.\d+)?)\b", blob, flags=re.I)
        return match.group(1) if match else ""
    match = re.search(r"(?<![A-Za-z0-9])([+-]\d+(?:\.\d+)?)(?![A-Za-z0-9])", blob)
    return match.group(1) if match else ""


def _note(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    text = re.sub(r"\bWeather:\s*Weather:\s*", "Weather: ", text, flags=re.I)
    text = re.sub(r"\bContext:\s*Context:\s*", "Context: ", text, flags=re.I)
    text = sanitize_public_text(text)
    lowered = text.rstrip(" .,:;-").lower()
    if any(lowered.endswith(end) for end in _DANGLING):
        text = trim_complete_sentence(text)
    return text


def normalize_row(value: Any) -> dict[str, Any]:
    data = _row(value)
    for key in _NOTE_KEYS:
        if key in data:
            cleaned = _note(data.get(key))
            if cleaned:
                data[key] = cleaned
    line = _line(data)
    fam = _family(data)
    if line:
        data["line"] = line
        data["point"] = line.lstrip("+")
        if fam == "total":
            data["total_line"] = line
        elif fam == "run_line":
            data["run_line"] = line
        elif fam == "spread":
            data["spread_line"] = line
    label = build_full_market_label(data)
    label = re.sub(r"\bSpread:\s*Point Spread:\s*", "Spread: ", label, flags=re.I)
    label = re.sub(r"\bRun Line:\s*Point Spread:\s*", "Run Line: ", label, flags=re.I)
    for key in ("aba_display_pick", "display_pick", "prediction", "pick", "exact_bet", "final_recommendation_label", "public_market_label", "verified_market_label", "full_market_label", "market_label", "trend_label"):
        data[key] = label
    edge = _num(data, "model_market_edge", "edge", "raw_edge", "two_page_raw_edge")
    ev = _num(data, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev", "raw_EV", "two_page_raw_EV")
    if edge is not None and abs(edge) > 1 and abs(edge) <= 100:
        edge = edge / 100.0
    negative = edge is not None and ev is not None and (edge <= 0 or ev <= 0)
    action = NO_PLAY if negative else public_action_label(data)
    if is_saved_source(data) and action == "VERIFIED CANDIDATE":
        action = "WATCHLIST"
    status = "No play / Research only / Price rejected" if negative else public_recommendation_status(data)
    for key in ("final_decision", "agent_decision", "recommendation", "consumer_action", "recommended_action"):
        data[key] = action
    data["risk"] = "PRICE REJECTED" if negative else "VERIFY PRICE"
    data["risk_level"] = data["risk_label"] = data["profit_guard_status"] = data["risk"]
    data["final_explanation"] = "Negative edge or EV at current price." if negative else status
    data["action_reason"] = data["recommendation_reason"] = data["final_explanation"]
    if is_saved_source(data):
        data["api_match_status"] = "Provider not matched"
        data["provider_match_status"] = "Provider not matched"
        data["verification_status"] = "Source saved"
        data["report_truth_warning"] = public_source_warning(data)
    return data


def install(module: Any) -> Any:
    if getattr(module, "_ABA_ACTIVE_EXPORT_GUARD", "") == VERSION:
        return module
    original_page = module.render_full_pick_magazine_page
    original_pages = module.render_full_magazine_book_pages
    original_pairs = getattr(module, "_pairs", None)
    original_api_lines = getattr(module, "api_provenance_lines", None)
    original_matchup_items = getattr(module, "_matchup_items", None)

    def guarded_page(pick: Any, *args: Any, **kwargs: Any):
        return original_page(normalize_row(pick), *args, **kwargs)

    def guarded_pages(picks: Iterable[Any], *args: Any, **kwargs: Any):
        return original_pages([normalize_row(row) for row in list(picks)], *args, **kwargs)

    def guarded_api_lines(row: Any) -> list[str]:
        data = normalize_row(row)
        try:
            configured = " · ".join(module.configured_api_sources())
        except Exception:
            configured = ""
        lines = ["Configured APIs: " + configured] if configured else []
        lines.append("Matched to this row: " + ("Saved source only" if is_saved_source(data) else "Provider matched"))
        return lines

    def guarded_pairs(row: Any, lang: str):
        data = normalize_row(row)
        pairs = [] if not callable(original_pairs) else list(original_pairs(data, lang))
        pairs = [("CONFIGURED APIS" if str(label).upper() == "ACTIVE APIS" else label, value) for label, value in pairs]
        pairs.append(("MATCHED", "Saved source only" if is_saved_source(data) else "Provider matched"))
        return pairs[:5]

    def guarded_matchup(row: Any):
        data = normalize_row(row)
        rows = [] if not callable(original_matchup_items) else list(original_matchup_items(data))
        out = [_note(item) for item in rows]
        return [item for item in out if item][:3] or ["Context was not returned for this event."]

    module.render_full_pick_magazine_page = guarded_page
    module.render_full_magazine_book_pages = guarded_pages
    module.api_provenance_lines = guarded_api_lines if callable(original_api_lines) else guarded_api_lines
    module._active_note = lambda row: guarded_api_lines(row)[-1] + "."
    module._pairs = guarded_pairs
    module._matchup_items = guarded_matchup
    try:
        from autonomous_betting_agent import magazine_second_page_patch as page2
        original_draw = page2._draw_second_page
        def guarded_second_page(patched: Any, pick: Any, *args: Any, **kwargs: Any):
            return original_draw(patched, normalize_row(pick), *args, **kwargs)
        page2._draw_second_page = guarded_second_page
    except Exception:
        pass
    module._ABA_ACTIVE_EXPORT_GUARD = VERSION
    return module
