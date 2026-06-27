from __future__ import annotations

from typing import Any, Iterable, Mapping

BAD = {"", "nan", "none", "null", "n/a", "na", "--"}


def row(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "to_dict"):
        data = value.to_dict()
        return data if isinstance(data, Mapping) else {}
    return getattr(value, "__dict__", {}) or {}


def text(data: Mapping[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = data.get(key)
        if value is not None and str(value).strip().lower() not in BAD:
            return str(value).strip()
    return default


def number(data: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = data.get(key)
        if value is None or str(value).strip().lower() in BAD:
            continue
        try:
            raw = str(value).replace("%", "").replace(",", "").strip()
            out = float(raw)
            if "%" in str(value) and abs(out) > 1:
                out /= 100
            return out
        except Exception:
            continue
    return None


def decimal_price(data: Mapping[str, Any]) -> float | None:
    price = number(data, "decimal_price", "odds", "best_price", "odds_at_pick")
    if price is None or price <= 0:
        return None
    return 1 + price / 100 if price >= 100 else price


def model_probability(data: Mapping[str, Any]) -> float | None:
    prob = number(data, "confidence", "model_probability", "final_probability", "model_probability_clean")
    if prob is None:
        return None
    if prob > 1:
        prob /= 100
    return max(0.0, min(prob, 0.98))


def market(data: Mapping[str, Any], language: str) -> str:
    blob = f"{text(data, 'market_type', 'bet_type', 'market')} {text(data, 'pick', 'prediction', 'selection', 'public_pick')}".lower()
    if "corner" in blob or "córner" in blob:
        return "Córners" if language == "es" else "Corners"
    if "btts" in blob or "both teams" in blob or "ambos" in blob:
        return "Ambos equipos anotan" if language == "es" else "Both Teams To Score"
    if "double chance" in blob or "doble oportunidad" in blob:
        return "Doble oportunidad" if language == "es" else "Double Chance"
    if "team total" in blob or "total de equipo" in blob:
        return "Total de equipo" if language == "es" else "Team Total"
    if "over" in blob or "under" in blob or "más de" in blob or "menos de" in blob:
        return "Más/Menos" if language == "es" else "Over/Under"
    if "home" in blob or "away" in blob or "local" in blob or "visitante" in blob:
        return "Local/Visitante" if language == "es" else "Home/Away"
    return text(data, "market_type", "bet_type", "market", default="Mercado" if language == "es" else "Market")


def item_ok(data: Mapping[str, Any], minimum: float) -> dict[str, Any] | None:
    price = decimal_price(data)
    conf = model_probability(data)
    edge = number(data, "model_market_edge", "edge")
    value = number(data, "expected_value_per_unit", "profit_expected_value", "expected_value", "ev")
    if edge is not None and abs(edge) > 1:
        edge /= 100
    if price is None or conf is None or conf < minimum:
        return None
    if (edge is not None and edge < 0) or (value is not None and value < 0):
        return None
    status = " ".join(str(data.get(key, "")) for key in ("learning_status", "consumer_action", "recommended_action", "data_issue_reason", "official_status_label")).lower()
    if any(token in status for token in ("blocked", "stale", "research only", "no play", "learning-blocked", "learning blocked")):
        return None
    out = dict(data)
    out["_ml_price"] = price
    out["_ml_conf"] = conf
    return out


def event_key(data: Mapping[str, Any]) -> str:
    return " ".join(text(data, "event", "public_event", "matchup", "event_name", default="unknown").lower().split())


def same_game_allowed(data: Mapping[str, Any]) -> bool:
    return str(data.get("same_game_parlay_compatible", data.get("same_game_combo_compatible", ""))).lower() in {"1", "true", "yes"}


def different_events_or_allowed(items: list[Mapping[str, Any]]) -> bool:
    seen: set[str] = set()
    for item in items:
        key = event_key(item)
        if key in seen and not same_game_allowed(item):
            return False
        seen.add(key)
    choices = " | ".join(text(item, "pick", "selection", "prediction", "public_pick").lower() for item in items)
    return not ("over" in choices and "under" in choices)


def build(rows: Iterable[Any]) -> dict[str, Any] | None:
    source = [dict(row(item)) for item in rows]
    for lane, threshold, count in (("safe_two", 0.62, 2), ("value_two", 0.58, 2), ("higher_three", 0.60, 3)):
        pool = [item_ok(item, threshold) for item in source]
        pool = [item for item in pool if item is not None]
        pool.sort(key=lambda item: (float(item["_ml_conf"]), float(item["_ml_price"])), reverse=True)
        chosen = pool[:count]
        if len(chosen) == count and different_events_or_allowed(chosen):
            combo_price = 1.0
            combo_conf = 1.0
            for item in chosen:
                combo_price *= float(item["_ml_price"])
                combo_conf *= float(item["_ml_conf"])
            combo_conf *= 0.92
            return {"lane": lane, "items": chosen, "price": combo_price, "confidence": combo_conf, "estimated_ev": combo_price * combo_conf - 1}
    return None


def label_lane(value: str, language: str) -> str:
    if language == "es":
        return {"safe_two": "Parlay más seguro de 2 selecciones", "value_two": "Parlay de valor de 2 selecciones", "higher_three": "Parlay de mayor riesgo de 3 selecciones"}.get(value, value)
    return {"safe_two": "Safer 2-leg parlay", "value_two": "Value 2-leg parlay", "higher_three": "Higher-risk 3-leg parlay"}.get(value, value)


def no_combo_items(language: str = "en", limit: int = 3) -> list[str]:
    if language == "es":
        return ["No se recomienda parlay", "No hay suficientes selecciones compatibles.", "Faltan cuotas verificadas."][:limit]
    return ["No parlay recommended", "Not enough compatible selections.", "Verified odds are missing."][:limit]


def _fmt_price(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _leg_label(item: Mapping[str, Any], language: str) -> str:
    choice = text(item, "pick", "selection", "prediction", "public_pick", default="Selection")
    return f"{choice} ({market(item, language)}) @ {_fmt_price(float(item['_ml_price']))}"


def _summary_line(built: Mapping[str, Any], language: str) -> str:
    price_label = "Cuota combinada" if language == "es" else "Combined odds"
    prob_label = "Probabilidad estimada" if language == "es" else "Estimated probability"
    return f"{price_label}: {_fmt_price(float(built['price']))} · {prob_label}: {float(built['confidence']):.0%}"


def format_items(rows: Iterable[Any], language: str = "en", limit: int = 3) -> list[str]:
    source = [dict(row(item)) for item in rows]
    built = build(source)
    if not built:
        return no_combo_items(language, limit)
    legs = [_leg_label(item, language) for item in built["items"]]
    if limit <= 2:
        return [label_lane(str(built["lane"]), language), _summary_line(built, language)][:limit]
    if limit == 3:
        joined_legs = " + ".join(legs[:2])
        return [label_lane(str(built["lane"]), language), joined_legs, _summary_line(built, language)]
    lines = [label_lane(str(built["lane"]), language), *legs, _summary_line(built, language)]
    return lines[:limit]


def attach_multi_leg_review(rows: Iterable[Any], language: str = "en") -> list[dict[str, Any]]:
    source = [dict(row(item)) for item in rows]
    if not source:
        return []
    joined = "|".join(format_items(source, language, 3))
    return [dict(item, combo_magazine_items=joined, parlay_magazine_items=joined) for item in source]
