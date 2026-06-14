from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from autonomous_betting_agent.sportsdataio_pipeline import run_sportsdataio_pipeline


class FakeClient:
    def raw_endpoint(self, endpoint, *, sport=None, subfeed=None):
        if subfeed == "scores":
            return [
                {
                    "GameID": 10,
                    "Season": 2026,
                    "Week": 1,
                    "DateTime": "2026-09-10T20:20:00",
                    "Status": "Final",
                    "HomeTeam": "DAL",
                    "AwayTeam": "NYG",
                    "HomeScore": 24,
                    "AwayScore": 17,
                }
            ]
        if subfeed == "stats":
            return [
                {
                    "PlayerID": 7,
                    "Name": "Jane Doe",
                    "Team": "DAL",
                    "Position": "RB",
                    "Season": 2026,
                    "Games": 10,
                    "RushingYards": 800,
                    "RushingAttempts": 150,
                    "Touchdowns": 8,
                }
            ]
        return []


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class SportsDataIOPipelineTests(unittest.TestCase):
    def test_pipeline_runs_fetch_results_features_props_and_profit_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            predictions = base / "predictions.csv"
            props = base / "props.csv"
            _write_csv(predictions, [{"sdio_game_id": "10", "prediction": "DAL", "best_price": "1.5", "closing_odds": "1.45"}])
            _write_csv(props, [{"sdio_player_id": "7", "player_name": "Jane Doe", "prop_type": "rushing yards", "line": "70", "selection": "over", "best_price": "1.8", "books": "8"}])

            report = run_sportsdataio_pipeline(
                client=FakeClient(),
                sport="nfl",
                games_endpoint="ScoresByDate/2026-SEP-10",
                player_stats_endpoint="PlayerSeasonStats/2026",
                predictions_csv=predictions,
                player_props_csv=props,
                output_dir=base / "out",
                include_watch=True,
                profit_goal_min_finished=1,
            )

            self.assertIn("fetch_games", report.steps_run)
            self.assertIn("apply_game_results", report.steps_run)
            self.assertIn("review_profit_goal", report.steps_run)
            self.assertIn("build_player_features", report.steps_run)
            self.assertIn("enrich_and_score_player_props", report.steps_run)
            self.assertEqual(report.counts["prediction_match_matched"], 1)
            self.assertEqual(report.counts["profit_goal_finished_rows"], 1)
            self.assertEqual(report.counts["profit_goal_wins"], 1)
            self.assertEqual(report.counts["player_feature_match_matched"], 1)
            self.assertTrue(Path(report.outputs.predictions_with_results_csv or "").exists())
            self.assertTrue(Path(report.outputs.profit_goal_report_json or "").exists())
            self.assertTrue(Path(report.outputs.player_props_checked_csv or "").exists())
            self.assertTrue(Path(report.outputs.report_json or "").exists())

    def test_pipeline_warns_when_predictions_have_no_games(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            predictions = base / "predictions.csv"
            _write_csv(predictions, [{"event": "NYG at DAL", "prediction": "DAL"}])
            report = run_sportsdataio_pipeline(predictions_csv=predictions, output_dir=base / "out")
            self.assertIn("predictions_csv supplied but no games endpoint or canonical games CSV was provided", report.warnings)

    def test_pipeline_can_use_existing_feature_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            features = base / "features.csv"
            props = base / "props.csv"
            _write_csv(features, [{"sdio_feature_player_id": "7", "display_name": "Jane Doe", "team": "DAL", "games": "10", "touchdowns_per_game": "0.8", "feature_ready": "true"}])
            _write_csv(props, [{"sdio_player_id": "7", "player_name": "Jane Doe", "prop_type": "touchdown", "selection": "yes", "best_price": "1.9", "books": "8"}])
            report = run_sportsdataio_pipeline(player_props_csv=props, existing_player_features_csv=features, output_dir=base / "out", include_watch=True)
            self.assertIn("use_existing_player_features", report.steps_run)
            self.assertEqual(report.counts["player_feature_match_matched"], 1)

    def test_pipeline_can_skip_profit_goal_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            predictions = base / "predictions.csv"
            _write_csv(predictions, [{"sdio_game_id": "10", "prediction": "DAL", "best_price": "1.5"}])
            report = run_sportsdataio_pipeline(
                client=FakeClient(),
                games_endpoint="ScoresByDate/2026-SEP-10",
                predictions_csv=predictions,
                output_dir=base / "out",
                run_profit_goal_review=False,
            )
            self.assertIn("apply_game_results", report.steps_run)
            self.assertNotIn("review_profit_goal", report.steps_run)
            self.assertIsNone(report.outputs.profit_goal_report_json)


if __name__ == "__main__":
    unittest.main()
