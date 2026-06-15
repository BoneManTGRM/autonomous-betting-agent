from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .audit import parse_float
from .row_normalizer import normalize_frame, safe_text

CORE_FIELDS = [
    'event',
    'sport',
    'market_type',
    'prediction',
    'model_probability',
    'decimal_price',
    'bookmaker',
    'odds_source',
    'prediction_timestamp',
    'event_start_utc',
    'decision',
    'confidence_tier',
    'model_version',
    'calibration_version',
    'memory_version',
    'api_bundle_version',
]

CONTEXT_HINTS = (
    'injury',
    'lineup',
    'weather',
    'rest',
    'travel',
    'ranking',
    'elo',
    'form',
    'pace',
    'pitcher',
    'goalie',
    'surface',
    'home',
    'away',
    'api',
    'news',
    'source',
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)


def snapshot_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode('utf-8')).hexdigest()


def snapshot_id(payload: dict[str, Any]) -> str:
    basis = '|'.join(safe_text(payload.get(field)) for field in ['event', 'market_type', 'prediction', 'prediction_timestamp', 'decimal_price'])
    return hashlib.sha256(basis.encode('utf-8')).hexdigest()[:24]


def context_columns(frame: pd.DataFrame) -> list[str]:
    if frame is None or frame.empty:
        return []
    columns: list[str] = []
    for column in frame.columns:
        key = str(column).lower()
        if column in CORE_FIELDS:
            continue
        if any(hint in key for hint in CONTEXT_HINTS):
            columns.append(column)
    return columns


def coverage_score(row: dict[str, Any], fields: list[str]) -> float:
    if not fields:
        return 0.0
    present = sum(1 for field in fields if safe_text(row.get(field)))
    return round(present / len(fields), 6)


def build_api_snapshots(frame: pd.DataFrame, *, created_at_utc: str | None = None) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    normalized = normalize_frame(frame)
    context_fields = context_columns(normalized)
    created_at = created_at_utc or utc_now_iso()
    rows: list[dict[str, Any]] = []
    for raw in normalized.to_dict(orient='records'):
        core = {field: raw.get(field, '') for field in CORE_FIELDS}
        context = {field: raw.get(field, '') for field in context_fields if safe_text(raw.get(field))}
        model_probability = parse_float(core.get('model_probability'))
        decimal_price = parse_float(core.get('decimal_price'))
        market_implied_probability = None if decimal_price is None or decimal_price <= 1 else round(1 / decimal_price, 6)
        edge = None
        if model_probability is not None and market_implied_probability is not None:
            if model_probability > 1:
                model_probability /= 100.0
            edge = round(model_probability - market_implied_probability, 6)
        payload = {
            'snapshot_schema_version': 'api-snapshot-memory-v1',
            'created_at_utc': created_at,
            'core': core,
            'context': context,
            'derived': {
                'market_implied_probability': market_implied_probability,
                'model_market_edge': edge,
                'core_coverage_score': coverage_score(core, CORE_FIELDS),
                'context_field_count': len(context),
                'context_coverage_score': coverage_score(raw, context_fields) if context_fields else 0.0,
            },
        }
        sid = snapshot_id(core)
        shash = snapshot_hash(payload)
        rows.append({
            'api_snapshot_id': sid,
            'api_snapshot_hash': shash,
            'snapshot_created_at_utc': created_at,
            'market_implied_probability': market_implied_probability,
            'model_market_edge': edge,
            'core_coverage_score': payload['derived']['core_coverage_score'],
            'context_field_count': len(context),
            'context_coverage_score': payload['derived']['context_coverage_score'],
            'snapshot_payload_json': _canonical_json(payload),
            **core,
        })
    return pd.DataFrame(rows)


def snapshot_memory_summary(frame: pd.DataFrame) -> dict[str, Any]:
    snapshots = build_api_snapshots(frame)
    if snapshots.empty:
        return {'rows': 0, 'avg_core_coverage': 0.0, 'avg_context_fields': 0.0, 'with_odds': 0, 'with_edge': 0}
    return {
        'rows': int(len(snapshots)),
        'avg_core_coverage': round(float(pd.to_numeric(snapshots['core_coverage_score'], errors='coerce').fillna(0).mean()), 3),
        'avg_context_fields': round(float(pd.to_numeric(snapshots['context_field_count'], errors='coerce').fillna(0).mean()), 3),
        'with_odds': int(snapshots['decimal_price'].fillna('').astype(str).str.strip().ne('').sum()),
        'with_edge': int(snapshots['model_market_edge'].notna().sum()),
    }


def export_snapshot_manifest(frame: pd.DataFrame) -> dict[str, Any]:
    snapshots = build_api_snapshots(frame)
    return {
        'summary': snapshot_memory_summary(frame),
        'snapshot_ids': snapshots.get('api_snapshot_id', pd.Series(dtype=str)).tolist(),
        'snapshot_hashes': snapshots.get('api_snapshot_hash', pd.Series(dtype=str)).tolist(),
    }
