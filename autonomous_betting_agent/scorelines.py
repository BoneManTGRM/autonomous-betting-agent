from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class ScorelinePick:
    home_score: int
    away_score: int
    probability: float

    @property
    def label(self) -> str:
        return f"{self.home_score}-{self.away_score}"

    @property
    def margin(self) -> int:
        return self.home_score - self.away_score


def _poisson(k: int, lam: float) -> float:
    lam = max(0.05, float(lam))
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def estimate_scorelines(home_xg: float, away_xg: float, max_goals: int = 6, top_n: int = 8) -> List[ScorelinePick]:
    picks: List[ScorelinePick] = []
    for home_score in range(max_goals + 1):
        home_prob = _poisson(home_score, home_xg)
        for away_score in range(max_goals + 1):
            prob = home_prob * _poisson(away_score, away_xg)
            picks.append(ScorelinePick(home_score, away_score, prob))
    picks.sort(key=lambda pick: pick.probability, reverse=True)
    return picks[:top_n]


def expected_goals_from_probability(home_probability: float, neutral_site: bool = False) -> tuple[float, float]:
    edge = max(-0.45, min(0.45, home_probability - 0.5))
    base_total = 2.55
    home_bias = 0.12 if not neutral_site else 0.0
    home_xg = base_total / 2 + edge * 1.2 + home_bias
    away_xg = base_total - home_xg
    return max(0.2, home_xg), max(0.2, away_xg)
