from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from autonomous_betting_agent.player_props import rank_player_props, apply_player_prop_layer


def main() -> int:
    parser = argparse.ArgumentParser(description="Score and rank individual player prop probabilities.")
    parser.add_argument("input_csv", type=Path)
    parser.add_argument("--ranked-output", type=Path, default=Path("data/player_props_ranked.csv"))
    parser.add_argument("--checked-output", type=Path, default=Path("data/player_props_checked.csv"))
    parser.add_argument("--include-watch", action="store_true")
    args = parser.parse_args()

    props = pd.read_csv(args.input_csv)
    checked = apply_player_prop_layer(props)
    ranked = rank_player_props(props, include_watch=args.include_watch)

    args.checked_output.parent.mkdir(parents=True, exist_ok=True)
    args.ranked_output.parent.mkdir(parents=True, exist_ok=True)
    checked.to_csv(args.checked_output, index=False)
    ranked.to_csv(args.ranked_output, index=False)
    print("Player prop review complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
