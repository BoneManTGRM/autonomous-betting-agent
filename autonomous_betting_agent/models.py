from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TeamSnapshot:
    name: str
    rating: float = 1500.0
    recent_form: float = 0.0
    injury_impact: float = 0.0
    rest_advantage: float = 0.0
    matchup_edge: float = 0.0
    weather_fit: float = 0.0
    data_completeness: float = 1.0
    source_count: int = 0
    notes: List[str] = field(default_factory=list)


@dataclass
class EventResearchInput:
    sport: str
    event_name: str
    home: TeamSnapshot
    away: TeamSnapshot
    neutral_site: bool = False
    home_market_price: Optional[float] = None
    away_market_price: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PredictionResult:
    event_name: str
    sport: str
    home_team: str
    away_team: str
    home_probability: float
    away_probability: float
    confidence: float
    favored_side: str
    evidence: List[str]
    warnings: List[str]
    market: Dict[str, Optional[float]]
    diagnostics: Dict[str, float]
    tgrm: Dict[str, Any]
