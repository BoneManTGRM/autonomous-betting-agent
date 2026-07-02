"""Autonomous Betting Agent package."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

APP_NAME = 'ABA Signal Pro'
APP_TAGLINE = 'Powered by Reparodynamics'
PREDICTOR_TOOL_NAME = 'Pro Predictor'


@dataclass(frozen=True)
class TeamSnapshot:
    name: str = ''
    rating: float = 1500.0
    recent_form: float = 0.0
    injury_impact: float = 0.0
    rest_advantage: float = 0.0
    matchup_edge: float = 0.0
    data_completeness: float = 1.0
    source_count: int = 0


@dataclass(frozen=True)
class EventResearchInput:
    sport: str
    event_name: str
    home: TeamSnapshot
    away: TeamSnapshot
    neutral_site: bool = False


@dataclass(frozen=True)
class AgentAnalysisResult:
    home_probability: float
    away_probability: float
    favored_side: str


class AutonomousBettingAgent:
    def analyze(self, event: EventResearchInput) -> AgentAnalysisResult:
        home_score = self._team_score(event.home)
        away_score = self._team_score(event.away)
        if not event.neutral_site:
            home_score += 0.03
        diff = home_score - away_score
        if abs(diff) < 1e-12:
            home_probability = 0.5
        else:
            home_probability = 1.0 / (1.0 + math.exp(-diff / 0.25))
        return AgentAnalysisResult(home_probability=home_probability, away_probability=1.0 - home_probability, favored_side=event.home.name if home_probability >= 0.5 else event.away.name)

    def _team_score(self, team: TeamSnapshot) -> float:
        completeness = max(0.1, min(1.0, team.data_completeness))
        base = (team.rating - 1500.0) / 400.0
        return base + 0.30 * team.recent_form - 0.25 * team.injury_impact + 0.15 * team.rest_advantage + 0.20 * team.matchup_edge + 0.02 * min(team.source_count, 5) * completeness


def _install_report_renderer_bridge() -> None:
    try:
        import importlib
    except Exception:
        return
    if getattr(importlib.import_module, '_ABA_REPORT_RENDERER_BRIDGE', False):
        return
    original = importlib.import_module

    def import_module_with_report_bridge(name: str, package: str | None = None):
        module = original(name, package)
        if name == 'autonomous_betting_agent.magazine_book_export':
            try:
                patcher = original('autonomous_betting_agent.active_magazine_export_guard')
                patcher.install(module)
            except Exception:
                pass
        return module

    import_module_with_report_bridge._ABA_REPORT_RENDERER_BRIDGE = True  # type: ignore[attr-defined]
    importlib.import_module = import_module_with_report_bridge


_install_report_renderer_bridge()
