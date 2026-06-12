from __future__ import annotations

import unittest

from autonomous_betting_agent import AutonomousBettingAgent, EventResearchInput, TeamSnapshot
from autonomous_betting_agent.market_math import implied_probability, normalize_two_way_market


class AgentTests(unittest.TestCase):
    def test_stronger_home_side_gets_higher_probability(self) -> None:
        event = EventResearchInput(
            sport="basketball",
            event_name="Home vs Away",
            home=TeamSnapshot(name="Home", rating=1600, recent_form=0.5, injury_impact=0.05, rest_advantage=0.2, matchup_edge=0.2, data_completeness=0.95, source_count=5),
            away=TeamSnapshot(name="Away", rating=1500, recent_form=0.0, injury_impact=0.2, rest_advantage=-0.1, matchup_edge=-0.1, data_completeness=0.9, source_count=5),
        )
        result = AutonomousBettingAgent().analyze(event)
        self.assertGreater(result.home_probability, 0.5)
        self.assertEqual(result.favored_side, "Home")
        self.assertAlmostEqual(result.home_probability + result.away_probability, 1.0)

    def test_equal_neutral_event_is_even(self) -> None:
        event = EventResearchInput(
            sport="tennis",
            event_name="A vs B",
            home=TeamSnapshot(name="A"),
            away=TeamSnapshot(name="B"),
            neutral_site=True,
        )
        result = AutonomousBettingAgent().analyze(event)
        self.assertAlmostEqual(result.home_probability, 0.5)
        self.assertAlmostEqual(result.away_probability, 0.5)

    def test_market_helpers(self) -> None:
        self.assertAlmostEqual(implied_probability(2.0), 0.5)
        home, away, overround = normalize_two_way_market(1.8, 2.1)
        self.assertIsNotNone(overround)
        assert home is not None and away is not None
        self.assertAlmostEqual(home + away, 1.0)


if __name__ == "__main__":
    unittest.main()
