from __future__ import annotations

import csv
import io
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.status_preview_service import build_status_preview_report


def _text(value: Any) -> str:
    return str(value or "").strip()


def _float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default


def parse_status_csv_text(csv_text: str | None) -> list[dict[str, str]]:
    text = _text(csv_text)
    if not text:
        return []
    reader = csv.DictReader(io.StringIO(text))
    return [{_text(key): _text(value) for key, value in row.items() if _text(key)} for row in reader]


def coerce_status_records(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows or []):
        records.append({
            "record_id": _text(row.get("record_id") or row.get("id") or row.get("proof_id") or f"record_{index + 1}"),
            "category": _text(row.get("category") or row.get("group") or row.get("sport") or row.get("league") or "general"),
            "name": _text(row.get("name") or row.get("event") or row.get("title") or row.get("matchup") or f"record_{index + 1}"),
            "time": _text(row.get("time") or row.get("date") or row.get("event_start_utc") or row.get("created_at_utc") or ""),
        })
    return records


def coerce_status_markers(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    for row in rows or []:
        primary = row.get("primary", row.get("primary_value", row.get("value_a")))
        secondary = row.get("secondary", row.get("secondary_value", row.get("value_b")))
        markers.append({
            "category": _text(row.get("category") or row.get("group") or row.get("sport") or row.get("league") or "general"),
            "name": _text(row.get("name") or row.get("event") or row.get("title") or row.get("matchup") or ""),
            "time": _text(row.get("time") or row.get("date") or row.get("event_start_utc") or row.get("created_at_utc") or ""),
            "source": _text(row.get("source") or row.get("provider") or "manual"),
            "primary": primary,
            "secondary": secondary,
            "confidence": _float(row.get("confidence"), 1.0 if primary not in (None, "") and secondary not in (None, "") else 0.0),
            "checked_at_utc": _text(row.get("checked_at_utc") or row.get("updated_at_utc") or ""),
        })
    return markers


def coerce_status_snapshots(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    for row in rows or []:
        snapshots.append({
            "category": _text(row.get("category") or row.get("group") or row.get("sport") or row.get("league") or "general"),
            "name": _text(row.get("name") or row.get("event") or row.get("title") or row.get("matchup") or ""),
            "time": _text(row.get("time") or row.get("date") or row.get("event_start_utc") or row.get("created_at_utc") or ""),
            "source": _text(row.get("source") or row.get("provider") or "manual"),
            "start_value": _float(row.get("start_value", row.get("original_value", row.get("locked_value"))), 0.0),
            "latest_value": _float(row.get("latest_value", row.get("current_value", row.get("final_value"))), 0.0),
        })
    return snapshots


def build_status_preview_from_sources(workspace_id: str | None = None, record_rows: Sequence[Mapping[str, Any]] | None = None, marker_rows: Sequence[Mapping[str, Any]] | None = None, snapshot_rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    return build_status_preview_report(
        workspace_id,
        coerce_status_records(record_rows or []),
        coerce_status_markers(marker_rows or []),
        coerce_status_snapshots(snapshot_rows or []),
    )


def build_status_preview_from_csv_text(workspace_id: str | None = None, record_csv: str | None = None, marker_csv: str | None = None, snapshot_csv: str | None = None) -> dict[str, Any]:
    return build_status_preview_from_sources(
        workspace_id,
        parse_status_csv_text(record_csv),
        parse_status_csv_text(marker_csv),
        parse_status_csv_text(snapshot_csv),
    )
