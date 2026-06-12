from __future__ import annotations

from .models import PredictionResult


def render_text(result: PredictionResult) -> str:
    return "\n".join([
        result.event_name,
        f"Sport: {result.sport}",
        f"Favored side: {result.favored_side}",
        f"Home: {result.home_probability:.1%}",
        f"Away: {result.away_probability:.1%}",
        f"Confidence: {result.confidence:.1%}",
    ]) + "\n"
