from __future__ import annotations

import csv
import io
from typing import Any

HIGH_CONFIDENCE_HINTS = (
    'high_confidence',
    'high confidence',
    'high-confidence',
    'alta_confianza',
    'alta confianza',
)


def detect_upload_context(data: bytes, filename: str, upload_type: str = 'auto') -> str:
    parts: list[str] = [filename or 'uploaded.csv']
    decoded = data.decode('utf-8-sig', errors='replace')
    try:
        reader = csv.DictReader(io.StringIO(decoded))
        for row_index, row in enumerate(reader):
            if row_index >= 25:
                break
            for key in ('source_file', 'source', 'note', 'result_note', 'decision_signals', 'agent_decision'):
                value = row.get(key)
                if value:
                    parts.append(str(value)[:140])
    except Exception:
        pass
    context = ' | '.join(parts)
    lowered = context.lower().replace('-', '_')
    if upload_type == 'fallback_high_confidence' or any(hint in lowered for hint in HIGH_CONFIDENCE_HINTS):
        context += ' | high confidence result only fallback high confidence'
    return context


def is_high_confidence_context(value: Any) -> bool:
    text = str(value or '').lower().replace('-', '_')
    return any(hint in text for hint in HIGH_CONFIDENCE_HINTS)
