from __future__ import annotations

from typing import Any

import pandas as pd

from .commercial_platform_tools import (
    dashboard_metrics,
    filter_locked_proof_rows,
    load_persistent_ledger,
    merge_ledgers,
    public_dashboard_table,
    report_card_markdown,
    save_persistent_ledger,
)
from .odds_lock_tools import daily_report, lock_rows, prepare_lock_candidates
from .row_normalizer import normalize_frame


def daily_workflow_preview(frame: pd.DataFrame | list[dict[str, Any]], *, include_watch: bool = False) -> dict[str, Any]:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    candidates = prepare_lock_candidates(normalized, include_watch=include_watch)
    return {
        'input_rows': int(len(normalized)),
        'candidate_rows': int(len(candidates)),
        'can_lock': bool(not candidates.empty),
    }


def run_daily_workflow(
    frame: pd.DataFrame | list[dict[str, Any]],
    *,
    analyst: str = 'Private Analytics',
    max_units: float = 2.0,
    include_watch: bool = False,
    save_to_persistent: bool = False,
    report_language: str = 'English',
) -> dict[str, Any]:
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    candidates = prepare_lock_candidates(normalized, include_watch=include_watch)
    locked = lock_rows(normalized, analyst=analyst, max_units=max_units, include_watch=include_watch)
    saved = pd.DataFrame()
    if save_to_persistent and not locked.empty:
        saved = save_persistent_ledger(merge_ledgers(load_persistent_ledger(), locked))
    active = saved if not saved.empty else filter_locked_proof_rows(locked)
    return {
        'input_rows': int(len(normalized)),
        'candidate_rows': int(len(candidates)),
        'locked_rows': int(len(active)),
        'saved_rows': int(len(saved)),
        'locked_frame': active,
        'public_frame': public_dashboard_table(active),
        'metrics': dashboard_metrics(active),
        'daily_report': daily_report(active, language=report_language, public_only=True),
        'report_card': report_card_markdown(active, brand=analyst),
    }


def workflow_stage_frame(result: dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame([
        {'stage': 'Input rows', 'rows': result.get('input_rows', 0), 'status': 'ready' if result.get('input_rows', 0) else 'empty'},
        {'stage': 'Lock candidates', 'rows': result.get('candidate_rows', 0), 'status': 'ready' if result.get('candidate_rows', 0) else 'none'},
        {'stage': 'Locked proof rows', 'rows': result.get('locked_rows', 0), 'status': 'ready' if result.get('locked_rows', 0) else 'none'},
        {'stage': 'Persistent saved rows', 'rows': result.get('saved_rows', 0), 'status': 'saved' if result.get('saved_rows', 0) else 'not_saved'},
    ])
