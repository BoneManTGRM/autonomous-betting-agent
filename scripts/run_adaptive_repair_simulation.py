"""Run the ABA Adaptive Repair Engine Phase 0-2 simulation on a CSV file."""

from __future__ import annotations

import argparse
from pathlib import Path

from autonomous_betting_agent.adaptive_repair_diagnostics import diagnostics_to_markdown, simulate_csv_diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ABA Adaptive Repair simulation on a graded CSV.")
    parser.add_argument("csv_path", help="Path to a graded CSV/export file")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of Markdown")
    parser.add_argument("--output", "-o", help="Optional path to save the Markdown or JSON report")
    parser.add_argument(
        "--fail-below-quality",
        type=float,
        default=None,
        help="Exit with status 2 if the data-quality score is below this threshold",
    )
    args = parser.parse_args()

    diagnostics = simulate_csv_diagnostics(Path(args.csv_path))
    output = diagnostics.to_json() if args.json else diagnostics_to_markdown(diagnostics)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)

    if args.fail_below_quality is not None and float(diagnostics.data_quality.get("score", 0.0)) < args.fail_below_quality:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
