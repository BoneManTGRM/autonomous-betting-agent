from typing import Any, Mapping, Sequence

import pandas as pd

from autonomous_betting_agent.profitability_metrics import profitability_summary
from autonomous_betting_agent.proof_performance_store import (
    SCHEMA_VERSION,
    append_performance_rows as _append_performance_rows,
    build_duplicate_key,
    build_proof_id,
    build_row_hash,
    export_performance_csv as _export_performance_csv,
    export_performance_json as _export_performance_json,
    normalize_performance_record,
    read_performance_ledger as _read_performance_ledger,
    read_recent_rows as _read_recent_rows,
    read_workspace_rows as _read_workspace_rows,
    validate_ledger_integrity as _validate_ledger_integrity,
)


def append_performance_rows(
    rows: pd.DataFrame | Sequence[Mapping[str, Any]],
    workspace_id: str,
    source_key: str | None = None,
    source_file: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    return _append_performance_rows(rows, workspace_id, source_key=source_key, source_file=source_file, dry_run=dry_run)


def read_performance_ledger(workspace_id: str | None = None) -> pd.DataFrame:
    return _read_performance_ledger(workspace_id=workspace_id)


def read_workspace_rows(workspace_id: str) -> pd.DataFrame:
    return _read_workspace_rows(workspace_id)


def read_recent_rows(workspace_id: str | None = None, limit: int = 100) -> pd.DataFrame:
    return _read_recent_rows(workspace_id=workspace_id, limit=limit)


def export_performance_csv(workspace_id: str | None = None, public_safe: bool = False) -> str:
    return _export_performance_csv(workspace_id=workspace_id, public_safe=public_safe)


def export_performance_json(workspace_id: str | None = None, public_safe: bool = False) -> str:
    return _export_performance_json(workspace_id=workspace_id, public_safe=public_safe)


def validate_ledger_integrity(workspace_id: str | None = None) -> dict[str, Any]:
    return _validate_ledger_integrity(workspace_id=workspace_id)


def _active_frame(frame: pd.DataFrame, include_corrections: bool = True) -> pd.DataFrame:
    if frame.empty or include_corrections:
        return frame.copy(deep=True)
    return frame[frame.get("record_type", "") != "correction"].copy(deep=True)


def rows_for_dashboard(workspace_id: str | None = None) -> pd.DataFrame:
    frame = read_performance_ledger(workspace_id=workspace_id)
    if frame.empty:
        return frame.copy(deep=True)
    rows = frame.copy(deep=True)
    rows["bookmaker"] = rows.get("sportsbook", "")
    rows["book"] = rows.get("sportsbook", "")
    rows["prediction"] = rows.get("pick", "")
    rows["public_pick"] = rows.get("pick", "")
    rows["public_event"] = rows.get("event", "")
    rows["model_market_edge"] = rows.get("edge", "")
    rows["expected_value_per_unit"] = rows.get("expected_value", "")
    rows["manual_clv"] = rows.get("clv", "")
    rows["decimal_price"] = rows.get("decimal_odds", "")
    rows["market"] = rows.get("market_type", "")
    return rows


def _last_updated(frame: pd.DataFrame) -> str:
    if frame.empty or "ingested_at_utc" not in frame.columns:
        return ""
    values = [str(value) for value in frame["ingested_at_utc"].tolist() if str(value).strip()]
    return max(values) if values else ""


def summarize_performance(workspace_id: str | None = None, include_corrections: bool = True) -> dict[str, Any]:
    ledger = read_performance_ledger(workspace_id=workspace_id)
    active = _active_frame(ledger, include_corrections=include_corrections)
    dashboard_rows = rows_for_dashboard(workspace_id=workspace_id)
    if not include_corrections and not dashboard_rows.empty:
        dashboard_rows = dashboard_rows[dashboard_rows.get("record_type", "") != "correction"].copy(deep=True)
    metrics = profitability_summary(dashboard_rows)
    integrity = validate_ledger_integrity(workspace_id=workspace_id)
    return {
        "total_rows": int(len(ledger)),
        "total_active_rows": int(len(active)),
        "unique_events": metrics.get("unique_event_count", 0),
        "duplicate_count": metrics.get("duplicate_count", 0),
        "correction_count": int((ledger.get("record_type", pd.Series(dtype=str)) == "correction").sum()) if not ledger.empty else 0,
        "wins": metrics.get("wins", 0),
        "losses": metrics.get("losses", 0),
        "pushes": metrics.get("pushes", 0),
        "cancels": metrics.get("cancels", 0),
        "win_rate_ex_push_cancel": metrics.get("win_rate_ex_push_cancel", 0.0),
        "profit_units": metrics.get("profit_units", 0.0),
        "risked_units": metrics.get("risked_units", 0.0),
        "roi": metrics.get("roi", 0.0),
        "average_odds": metrics.get("average_odds"),
        "average_edge": metrics.get("average_edge"),
        "average_no_vig_edge": metrics.get("average_no_vig_edge"),
        "average_clv": metrics.get("average_clv"),
        "playable_roi": metrics.get("playable_pick_roi", {}),
        "watchlist_roi": metrics.get("watchlist_pick_roi", {}),
        "avoid_tracking_result": metrics.get("avoid_pick_tracking_result", {}),
        "duplicate_adjusted_record": metrics.get("duplicate_adjusted_record", {}),
        "last_updated_timestamp": _last_updated(ledger),
        "schema_version": SCHEMA_VERSION,
        "ledger_integrity_status": integrity.get("status", "PASS"),
        "ledger_integrity": integrity,
    }
