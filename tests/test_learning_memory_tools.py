from __future__ import annotations

import unittest

from autonomous_betting_agent.learning_memory_tools import memory_metrics, read_compact_csv_bytes


class LearningMemoryToolsTests(unittest.TestCase):
    def test_high_confidence_result_only_file_uses_fallback_probability(self) -> None:
        csv_text = "event,sport,prediction,result\nA at B,Soccer,B,won\nC at D,Soccer,C,lost\nE at F,Soccer,E,unknown\n"
        rows, stats = read_compact_csv_bytes(csv_text.encode("utf-8"), "High confidence.csv")
        self.assertEqual(stats["input_rows"], 3)
        self.assertEqual(stats["usable_rows"], 2)
        self.assertEqual(stats["wins"], 1)
        self.assertEqual(stats["losses"], 1)
        self.assertEqual(stats["missing_result"], 1)
        self.assertEqual(stats["fallback_probability_rows"], 2)
        self.assertTrue(all(row["probability_source"] == "fallback_high_confidence" for row in rows))
        metrics = memory_metrics(rows)
        self.assertEqual(metrics["resolved"], 2)
        self.assertEqual(metrics["wins"], 1)
        self.assertEqual(metrics["losses"], 1)

    def test_explicit_probability_does_not_need_fallback(self) -> None:
        csv_text = "event,prediction,model_probability,result\nA at B,B,62%,won\n"
        rows, stats = read_compact_csv_bytes(csv_text.encode("utf-8"), "regular.csv")
        self.assertEqual(stats["usable_rows"], 1)
        self.assertEqual(stats["fallback_probability_rows"], 0)
        self.assertEqual(rows[0]["probability_source"], "model_probability")
        self.assertAlmostEqual(rows[0]["probability"], 0.62)


if __name__ == "__main__":
    unittest.main()
