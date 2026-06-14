from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from autonomous_betting_agent.prediction_audit import audit_predictions


def main() -> int:
    parser = argparse.ArgumentParser(description="Review a prediction CSV and write checked outputs.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--checked-output", type=Path, default=Path("data/predictions_checked.csv"))
    parser.add_argument("--deduped-output", type=Path, default=Path("data/predictions_checked_deduped.csv"))
    parser.add_argument("--report-output", type=Path, default=Path("data/predictions_review_report.json"))
    args = parser.parse_args()

    rows = pd.read_csv(args.input_csv)
    checked, deduped, report = audit_predictions(rows)

    for output_path in (args.checked_output, args.deduped_output, args.report_output):
        output_path.parent.mkdir(parents=True, exist_ok=True)

    checked.to_csv(args.checked_output, index=False)
    deduped.to_csv(args.deduped_output, index=False)
    args.report_output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print("Review complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
