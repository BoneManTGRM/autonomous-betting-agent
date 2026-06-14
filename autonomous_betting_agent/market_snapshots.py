from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .live_odds import LiveEventSummary

SNAPSHOT_COLUMNS = [
    "snapshot_time_utc",
    "event_id",
    "sport_key",
    "sport_title",
    "commence_time",
    "home_team",
    "away_team",
    "outcome",
    "is_favorite",
    "normalized_probability",
    "raw_probability",
    "average_price",
    "best_price",
    "worst_price",
    "price_range",
    "best_bookmaker",
    "source_count",
    "bookmaker_count",
    "market_overround",
]

MOVEMENT_COLUMNS = [
    "opening_probability",
    "current_probability",
    "probability_move",
    "opening_best_price",
    "current_best_price",
    "best_price_move",
    "opening_snapshot_time_utc",
    "latest_snapshot_time_utc",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def event_snapshot_rows(summary: LiveEventSummary, snapshot_time_utc: str | None = None) -> list[dict[str, Any]]:
    taken_at = snapshot_time_utc or utc_now_iso()
    rows: list[dict[str, Any]] = []
    for outcome in summary.outcomes:
        rows.append({
            "snapshot_time_utc": taken_at,
            "event_id": summary.event_id,
            "sport_key": summary.sport_key,
            "sport_title": summary.sport_title,
            "commence_time": summary.commence_time,
            "home_team": summary.home_team,
            "away_team": summary.away_team,
            "outcome": outcome.name,
            "is_favorite": outcome.name == summary.favorite,
            "normalized_probability": outcome.normalized_probability,
            "raw_probability": outcome.raw_probability,
            "average_price": outcome.average_price,
            "best_price": outcome.best_price,
            "worst_price": outcome.worst_price,
            "price_range": outcome.price_range,
            "best_bookmaker": outcome.best_bookmaker,
            "source_count": outcome.source_count,
            "bookmaker_count": summary.bookmaker_count,
            "market_overround": summary.market_overround,
        })
    return rows


def summaries_to_snapshot_frame(summaries: Iterable[LiveEventSummary], snapshot_time_utc: str | None = None) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    taken_at = snapshot_time_utc or utc_now_iso()
    for summary in summaries:
        rows.extend(event_snapshot_rows(summary, taken_at))
    return pd.DataFrame(rows, columns=SNAPSHOT_COLUMNS)


def append_snapshot_csv(rows: pd.DataFrame, path: str | Path) -> pd.DataFrame:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        existing = pd.read_csv(output_path)
        combined = pd.concat([existing, rows], ignore_index=True)
    else:
        combined = rows.copy()
    combined.to_csv(output_path, index=False)
    return combined


def add_line_movement(snapshot_frame: pd.DataFrame) -> pd.DataFrame:
    if snapshot_frame.empty:
        out = snapshot_frame.copy()
        for column in MOVEMENT_COLUMNS:
            out[column] = pd.Series(dtype="object")
        return out

    work = snapshot_frame.copy()
    work["snapshot_time_utc"] = work["snapshot_time_utc"].astype(str)
    sort_cols = ["event_id", "outcome", "snapshot_time_utc"]
    work = work.sort_values(sort_cols).reset_index(drop=True)
    group_cols = ["event_id", "outcome"]
    first = work.groupby(group_cols, dropna=False).first().reset_index()
    last = work.groupby(group_cols, dropna=False).last().reset_index()
    movement = first[group_cols + ["normalized_probability", "best_price", "snapshot_time_utc"]].merge(
        last[group_cols + ["normalized_probability", "best_price", "snapshot_time_utc"]],
        on=group_cols,
        suffixes=("_opening", "_current"),
    )
    movement["opening_probability"] = movement["normalized_probability_opening"]
    movement["current_probability"] = movement["normalized_probability_current"]
    movement["probability_move"] = movement["current_probability"] - movement["opening_probability"]
    movement["opening_best_price"] = movement["best_price_opening"]
    movement["current_best_price"] = movement["best_price_current"]
    movement["best_price_move"] = movement["current_best_price"] - movement["opening_best_price"]
    movement["opening_snapshot_time_utc"] = movement["snapshot_time_utc_opening"]
    movement["latest_snapshot_time_utc"] = movement["snapshot_time_utc_current"]
    keep = group_cols + MOVEMENT_COLUMNS
    return work.merge(movement[keep], on=group_cols, how="left")


def latest_snapshot_with_movement(snapshot_frame: pd.DataFrame) -> pd.DataFrame:
    moved = add_line_movement(snapshot_frame)
    if moved.empty:
        return moved
    moved = moved.sort_values(["event_id", "outcome", "snapshot_time_utc"])
    return moved.groupby(["event_id", "outcome"], dropna=False).tail(1).reset_index(drop=True)
