"""Local calibration helpers for graded proof rows."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _result_value(row: Mapping[str, Any]) -> float | None:
    grade = str(row.get("grade") or row.get("result") or "").strip().lower()
    if grade in {"win", "won", "w"}:
        return 1.0
    if grade in {"loss", "lost", "l"}:
        return 0.0
    return None


def row_probability(row: Mapping[str, Any]) -> float | None:
    return _float(row.get("learned_model_probability") or row.get("model_probability") or row.get("probability"))


def brier_score(rows: Iterable[Mapping[str, Any]]) -> float | None:
    errors: list[float] = []
    for row in rows:
        probability = row_probability(row)
        result = _result_value(row)
        if probability is None or result is None:
            continue
        if probability > 1:
            probability = probability / 100.0
        if 0 <= probability <= 1:
            errors.append((probability - result) ** 2)
    return sum(errors) / len(errors) if errors else None


def calibration_buckets(rows: Iterable[Mapping[str, Any]], bucket_size: float = 0.10) -> list[dict[str, Any]]:
    buckets: dict[int, list[tuple[float, float]]] = defaultdict(list)
    for row in rows:
        probability = row_probability(row)
        result = _result_value(row)
        if probability is None or result is None:
            continue
        if probability > 1:
            probability = probability / 100.0
        if not 0 <= probability <= 1:
            continue
        bucket = int(min(0.999, probability) / bucket_size)
        buckets[bucket].append((probability, result))

    output: list[dict[str, Any]] = []
    for bucket, values in sorted(buckets.items()):
        expected = sum(item[0] for item in values) / len(values)
        actual = sum(item[1] for item in values) / len(values)
        output.append(
            {
                "bucket": f"{bucket * bucket_size:.0%}-{(bucket + 1) * bucket_size:.0%}",
                "sample_size": len(values),
                "expected_win_rate": expected,
                "actual_win_rate": actual,
                "gap": actual - expected,
            }
        )
    return output


def odds_band_summary(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    bands = {
        "<1.30": [],
        "1.30-1.59": [],
        "1.60-1.89": [],
        "1.90-2.24": [],
        "2.25-2.99": [],
        "3.00+": [],
    }
    for row in rows:
        price = _float(row.get("decimal_price") or row.get("odds_at_pick"))
        result = _result_value(row)
        if price is None or result is None:
            continue
        if price < 1.30:
            key = "<1.30"
        elif price < 1.60:
            key = "1.30-1.59"
        elif price < 1.90:
            key = "1.60-1.89"
        elif price < 2.25:
            key = "1.90-2.24"
        elif price < 3.00:
            key = "2.25-2.99"
        else:
            key = "3.00+"
        bands[key].append(result)
    output = []
    for key, values in bands.items():
        output.append({"odds_band": key, "sample_size": len(values), "win_rate": (sum(values) / len(values) if values else None)})
    return output
