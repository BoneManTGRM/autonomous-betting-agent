from __future__ import annotations

from typing import Any, Mapping

from autonomous_betting_agent.model_status_utils import PROB_FIELDS, clean


def outcome_value(value: Any) -> str:
    text = clean(value).lower().replace("-", "_").replace(" ", "_")
    if text in {"win", "won", "w", "correct", "hit"}:
        return "win"
    if text in {"loss", "lost", "l", "incorrect", "miss"}:
        return "loss"
    if text in {"push", "void", "tie", "draw"}:
        return "push"
    if text in {"cancel", "cancelled", "canceled"}:
        return "cancel"
    if text in {"", "pending", "open", "ungraded", "not_started", "in_progress"}:
        return "pending"
    return "unknown"


def probability_value(row: Mapping[str, Any]) -> float | None:
    for field in PROB_FIELDS:
        try:
            value = float(str(row.get(field)).strip())
        except (TypeError, ValueError):
            continue
        if value > 1.0 and value <= 100.0:
            value /= 100.0
        return max(0.0, min(1.0, value))
    return None


def brier_score(rows: list[dict[str, Any]], result_field: str | None) -> tuple[bool, float | None]:
    pairs = []
    for row in rows:
        result = outcome_value(row.get(result_field)) if result_field else "pending"
        prob = probability_value(row)
        if result in {"win", "loss"} and prob is not None:
            pairs.append((prob, int(result == "win")))
    if not pairs:
        return False, None
    return True, round(sum((prob - actual) ** 2 for prob, actual in pairs) / len(pairs), 6)
