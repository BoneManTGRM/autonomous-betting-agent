from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from .row_normalizer import normalize_frame, safe_text

PENDING_STATUSES = {'', 'pending', 'unknown', 'scheduled', 'live', 'needs_review'}
VOID_STATUSES = {'void', 'push', 'pushed', 'cancelled', 'canceled', 'postponed', 'abandoned', 'no_action'}
RESOLVED_PICK_STATUSES = {'win', 'loss'}
COMPLETED_EVENT_STATUSES = RESOLVED_PICK_STATUSES | {'void'}
EVENT_ID_FIELDS = ('event_id', 'game_id', 'match_id', 'fixture_id')
EVENT_FALLBACK_FIELDS = ('sport_key', 'sport', 'league', 'event_start_utc', 'event_date', 'event', 'home_team', 'away_team')


def _status(value: Any) -> str:
    text = safe_text(value).lower()
    if text in {'won', 'w', 'correct', 'hit'}:
        return 'win'
    if text in {'lost', 'l', 'incorrect', 'miss'}:
        return 'loss'
    if text in VOID_STATUSES:
        return 'void'
    if text in PENDING_STATUSES:
        return 'pending'
    return text or 'pending'


def event_identity_key(row: Mapping[str, Any]) -> str:
    """Return the real-world event key used to group correlated pick rows."""
    for field in EVENT_ID_FIELDS:
        value = safe_text(row.get(field))
        if value:
            return f'event_id:{value}'
    parts = [safe_text(row.get(field)).lower() for field in EVENT_FALLBACK_FIELDS]
    parts = [part for part in parts if part]
    if parts:
        return 'event:' + '|'.join(parts)
    return 'event:unknown'


def add_event_exposure_columns(frame: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    """Add event/correlation columns without collapsing separate markets from the same game."""
    raw = pd.DataFrame(frame) if isinstance(frame, list) else frame
    normalized = normalize_frame(raw) if raw is not None and not raw.empty else pd.DataFrame()
    if normalized.empty:
        return pd.DataFrame()
    out = normalized.copy()
    keys = [event_identity_key(row) for row in out.to_dict(orient='records')]
    out['unique_event_id'] = keys
    out['correlation_group_id'] = keys
    counts = out.groupby('unique_event_id')['unique_event_id'].transform('size').astype(int)
    out['same_event_pick_count'] = counts
    out['event_pick_index'] = out.groupby('unique_event_id').cumcount().add(1).astype(int)
    out['is_multi_market_event'] = counts.gt(1)
    out['event_count_weight'] = (1.0 / counts).round(6)
    return out


def pick_level_metrics(frame: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    exposed = add_event_exposure_columns(frame)
    if exposed.empty:
        return {
            'pick_rows': 0, 'resolved_pick_rows': 0, 'wins': 0, 'losses': 0,
            'voids': 0, 'pending_pick_rows': 0, 'pick_hit_rate_excluding_voids': None,
        }
    status = exposed.get('result_status', pd.Series(dtype=str)).map(_status)
    wins = int(status.eq('win').sum())
    losses = int(status.eq('loss').sum())
    voids = int(status.eq('void').sum())
    resolved = wins + losses
    pending = int(status.isin(PENDING_STATUSES | {'pending'}).sum())
    return {
        'pick_rows': int(len(exposed)),
        'resolved_pick_rows': resolved,
        'wins': wins,
        'losses': losses,
        'voids': voids,
        'pending_pick_rows': pending,
        'pick_hit_rate_excluding_voids': None if resolved == 0 else round(wins / resolved, 6),
    }


def event_level_metrics(frame: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    exposed = add_event_exposure_columns(frame)
    if exposed.empty:
        return {
            'unique_events': 0, 'completed_events': 0, 'pending_events': 0,
            'events_with_multiple_pick_rows': 0, 'extra_same_event_pick_rows': 0,
            'max_pick_rows_per_event': 0,
        }
    status = exposed.get('result_status', pd.Series(dtype=str)).map(_status)
    exposed = exposed.assign(_event_result_status=status)
    grouped = exposed.groupby('unique_event_id', dropna=False)
    event_sizes = grouped.size()
    completed = grouped['_event_result_status'].apply(lambda s: bool(s.isin(COMPLETED_EVENT_STATUSES).any()))
    unique_events = int(len(event_sizes))
    completed_count = int(completed.sum())
    return {
        'unique_events': unique_events,
        'completed_events': completed_count,
        'pending_events': int(unique_events - completed_count),
        'events_with_multiple_pick_rows': int(event_sizes.gt(1).sum()),
        'extra_same_event_pick_rows': int(len(exposed) - unique_events),
        'max_pick_rows_per_event': int(event_sizes.max()) if not event_sizes.empty else 0,
    }


def exposure_metrics(frame: pd.DataFrame | list[dict[str, Any]]) -> dict[str, Any]:
    out = event_level_metrics(frame)
    out.update(pick_level_metrics(frame))
    out['row_level_record'] = f"{out['wins']}-{out['losses']}"
    out['row_level_win_rate'] = out['pick_hit_rate_excluding_voids']
    return out
