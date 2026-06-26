"""Run the ABA Adaptive Repair Engine Phase 0-2 simulation on a CSV file."""

from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.adaptive_repair_engine import report_to_markdown, simulate_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ABA Adaptive Repair simulation on a graded CSV.")
    parser.add_argument("csv_path", help="Path to a graded CSV/export file")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    args = parser.parse_args()

    report = simulate_csv(Path(args.csv_path))
    if args.json:
        print(report.to_json())
    else:
        print(report_to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
