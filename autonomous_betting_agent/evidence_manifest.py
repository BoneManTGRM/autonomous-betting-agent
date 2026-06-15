from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or '').encode('utf-8')).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), default=str, ensure_ascii=False)


def hash_json(value: Any) -> str:
    return sha256_text(canonical_json(value))


def hash_frame(frame: pd.DataFrame) -> str:
    if frame is None or frame.empty:
        return sha256_text('empty-frame')
    records = frame.fillna('').astype(str).to_dict(orient='records')
    return hash_json(records)


def build_evidence_manifest(*, memory_bank: Mapping[str, Any] | None = None, ledger: pd.DataFrame | None = None, snapshots: pd.DataFrame | None = None, proof_summary: Mapping[str, Any] | None = None) -> dict[str, Any]:
    memory_bank = dict(memory_bank or {})
    ledger_rows = 0 if ledger is None else int(len(ledger))
    snapshot_rows = 0 if snapshots is None else int(len(snapshots))
    manifest = {
        'manifest_version': 'evidence-manifest-v1',
        'generated_at_utc': datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z'),
        'artifacts': {
            'learning_memory_bank': {
                'rows': len(memory_bank.get('compact_rows', [])) if isinstance(memory_bank.get('compact_rows'), list) else 0,
                'sha256': hash_json(memory_bank),
                'source': memory_bank.get('global_calibrator', {}).get('source') if isinstance(memory_bank.get('global_calibrator'), dict) else memory_bank.get('source'),
                'training_mode': memory_bank.get('training_mode'),
            },
            'proof_ledger': {
                'rows': ledger_rows,
                'sha256': hash_frame(ledger if ledger is not None else pd.DataFrame()),
            },
            'prediction_snapshots': {
                'rows': snapshot_rows,
                'sha256': hash_frame(snapshots if snapshots is not None else pd.DataFrame()),
            },
            'proof_readiness_summary': {
                'sha256': hash_json(dict(proof_summary or {})),
                'summary': dict(proof_summary or {}),
            },
        },
        'honest_use_note': 'This manifest fingerprints current local evidence. It does not prove historical picks were timestamped before games unless those rows also have official locked odds/probability snapshots.',
    }
    manifest['manifest_sha256'] = hash_json(manifest['artifacts'])
    return manifest


def manifest_markdown(manifest: Mapping[str, Any]) -> str:
    artifacts = manifest.get('artifacts', {}) if isinstance(manifest, dict) else {}
    lines = [
        '# Evidence Manifest',
        '',
        f"Generated: {manifest.get('generated_at_utc', '')}",
        f"Manifest SHA-256: `{manifest.get('manifest_sha256', '')}`",
        '',
        '## Artifacts',
        '| Artifact | Rows | SHA-256 |',
        '|---|---:|---|',
    ]
    for name, info in artifacts.items():
        if isinstance(info, dict):
            lines.append(f"| {name} | {info.get('rows', '')} | `{info.get('sha256', '')}` |")
    lines.extend([
        '',
        '## Honest Use Note',
        str(manifest.get('honest_use_note', '')),
    ])
    return '\n'.join(lines) + '\n'
