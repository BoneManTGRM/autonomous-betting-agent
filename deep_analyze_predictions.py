from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from autonomous_betting_agent.deep_analysis import apply_deep_analysis, merge_latest_movement


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply deep ARA odds/weather/movement analysis to prediction rows.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--movement-csv", type=Path, default=None, help="Optional latest_market_movement.csv file.")
    parser.add_argument("--output", type=Path, default=Path("data/deep_ara_analysis.csv"))
    parser.add_argument("--top-output", type=Path, default=Path("data/deep_ara_top_rows.csv"))
    parser.add_argument("--top-n", type=int, default=25)
    args = parser.parse_args()

    frame = pd.read_csv(args.input_csv)
    if args.movement_csv and args.movement_csv.exists():
        movement = pd.read_csv(args.movement_csv)
        frame = merge_latest_movement(frame, movement)
    enriched = apply_deep_analysis(frame)
    top = enriched.sort_values(["ara_deep_score"], ascending=False).head(args.top_n)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.top_output.parent.mkdir(parents=True, exist_ok=True)
    enriched.to_csv(args.output, index=False)
    top.to_csv(args.top_output, index=False)
    print(f"Saved deep analysis to {args.output}")
    print(f"Saved top rows to {args.top_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
