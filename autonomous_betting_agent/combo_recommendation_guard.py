from __future__ import annotations

from typing import Any, Iterable

ES_NO_COMBO = "No se recomienda parlay"
EN_NO_COMBO = "No parlay recommended"


def combo_guard_items(rows: Iterable[Any], language: str = "en") -> list[str]:
    if language == "es":
        return [ES_NO_COMBO, "No hay suficientes selecciones compatibles.", "Faltan cuotas verificadas."]
    return [EN_NO_COMBO, "Not enough compatible selections.", "Verified odds are missing."]
