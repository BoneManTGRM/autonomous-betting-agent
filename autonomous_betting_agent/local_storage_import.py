from __future__ import annotations

import csv
import hashlib
import io
import json
from typing import Any, Mapping, Sequence

from autonomous_betting_agent.ledger_types import LEDGER_TYPES, RESEARCH_LEDGER
from autonomous_betting_agent.storage import LocalStorage

LOCAL_STORAGE_SAFETY_DETAIL = "local storage only; no model mutation; no live learning activation; no Reparodynamics repair activation"
DEFAULT_IMPORT_ACTION = "local_storage_import"
REPARODYNAMICS_IMPORT_ACTION = "reparodynamics_rows_saved_to_research"

_IDENTITY_FIELDS: tuple[tuple[str, ...], ...] = (
    ("proof_id",),
    ("event", "game", "match", "event_name", "matchup"),
    ("prediction", "pick", "selection"),
    ("market_type", "market", "bet_type"),
    ("decimal_price", "odds", "best_price"),
    ("result", "grade", "result_status"),
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalized(value: Any) -> str:
    return " ".join(_text(value).lower().split())


def _first_value(row: Mapping[str, Any], keys: Sequence[str]) -> str:
    for key in keys:
        value = _text(row.get(key))
        if value:
            return value
    return ""


def parse_uploaded_csv_bytes(file_bytes: bytes) -> list[dict[str, Any]]:
    """Parse an uploaded CSV into dictionaries without saving or learning."""

    text = (file_bytes or b"").decode("utf-8-sig", errors="replace")
    if not text.strip():
        return []
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def stable_row_identity(row: Mapping[str, Any]) -> str:
    """Return a stable, non-secret identity used only for local import dedupe."""

    proof_id = _normalized(row.get("proof_id"))
    if proof_id:
        return "proof_id:" + proof_id
    payload = {
        "+".join(keys): _normalized(_first_value(row, keys))
        for keys in _IDENTITY_FIELDS[1:]
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return "row:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _empty_result(*, rows_seen: int, ledger_type: str, filename: str, source: str, preview_only: bool, confirmed: bool, message: str) -> dict[str, Any]:
    return {
        "rows_seen": int(rows_seen),
        "rows_imported": 0,
        "rows_skipped_duplicate": 0,
        "ledger_type": ledger_type,
        "filename": filename,
        "source": source,
        "preview_only": bool(preview_only),
        "confirmed": bool(confirmed),
        "audit_written": False,
        "saved_locally_only": True,
        "live_mutation": False,
        "model_training": False,
        "message": message,
    }


def _storage_or_default(storage: object | None) -> Any:
    return storage if storage is not None else LocalStorage()


def _existing_identities(storage: Any, ledger_type: str) -> set[str]:
    try:
        existing = storage.load_rows(ledger_type)
    except Exception:
        existing = []
    return {stable_row_identity(row) for row in existing}


def _dedupe_rows(rows: Sequence[Mapping[str, Any]], existing: set[str], *, dedupe: bool) -> tuple[list[dict[str, Any]], int]:
    if not dedupe:
        return [dict(row) for row in rows], 0
    seen = set(existing)
    output: list[dict[str, Any]] = []
    skipped = 0
    for row in rows:
        identity = stable_row_identity(row)
        if identity in seen:
            skipped += 1
            continue
        seen.add(identity)
        output.append(dict(row))
    return output, skipped


def _write_audit(storage: Any, *, action: str, detail: str) -> bool:
    audit = getattr(storage, "add_audit_event", None)
    if not callable(audit):
        return False
    audit(action=action, row={"proof_id": ""}, detail=detail)
    return True


def import_rows_to_local_storage(
    rows: list[dict[str, Any]],
    ledger_type: str = RESEARCH_LEDGER,
    filename: str = "",
    source: str = "manual_upload",
    preview_only: bool = True,
    confirmed: bool = False,
    dedupe: bool = True,
    storage: object | None = None,
    audit_action: str = DEFAULT_IMPORT_ACTION,
    audit_extra: str = "",
) -> dict[str, Any]:
    """Safely import rows into local proof storage without live learning or mutation."""

    safe_rows = [dict(row) for row in rows or []]
    rows_seen = len(safe_rows)
    ledger = _text(ledger_type) or RESEARCH_LEDGER
    if ledger not in LEDGER_TYPES:
        return _empty_result(
            rows_seen=rows_seen,
            ledger_type=ledger,
            filename=filename,
            source=source,
            preview_only=preview_only,
            confirmed=confirmed,
            message=f"Invalid ledger type: {ledger}",
        )

    store = _storage_or_default(storage)
    existing = _existing_identities(store, ledger)
    importable_rows, skipped = _dedupe_rows(safe_rows, existing, dedupe=dedupe)

    if preview_only:
        result = _empty_result(
            rows_seen=rows_seen,
            ledger_type=ledger,
            filename=filename,
            source=source,
            preview_only=preview_only,
            confirmed=confirmed,
            message="Preview only; no rows saved.",
        )
        result["rows_skipped_duplicate"] = skipped
        return result

    if not confirmed:
        result = _empty_result(
            rows_seen=rows_seen,
            ledger_type=ledger,
            filename=filename,
            source=source,
            preview_only=preview_only,
            confirmed=confirmed,
            message="Confirmation required; no rows saved.",
        )
        result["rows_skipped_duplicate"] = skipped
        return result

    imported = 0
    if importable_rows:
        store.save_rows(importable_rows, ledger_type=ledger)
        imported = len(importable_rows)

    detail = (
        f"{audit_extra}rows_seen={rows_seen}; rows_imported={imported}; "
        f"rows_skipped_duplicate={skipped}; ledger_type={ledger}; filename={filename}; "
        f"source={source}; {LOCAL_STORAGE_SAFETY_DETAIL}"
    )
    audit_written = _write_audit(store, action=audit_action, detail=detail)
    return {
        "rows_seen": rows_seen,
        "rows_imported": imported,
        "rows_skipped_duplicate": skipped,
        "ledger_type": ledger,
        "filename": filename,
        "source": source,
        "preview_only": False,
        "confirmed": True,
        "audit_written": audit_written,
        "saved_locally_only": True,
        "live_mutation": False,
        "model_training": False,
        "message": f"Imported {imported} row(s) to {ledger}; skipped {skipped} duplicate row(s).",
    }


def save_reparodynamics_rows_to_research(
    rows: list[dict[str, Any]],
    *,
    run_id: str = "",
    filename: str = "reparodynamics_scan.csv",
    confirmed: bool = False,
    dedupe: bool = True,
    storage: object | None = None,
) -> dict[str, Any]:
    return import_rows_to_local_storage(
        rows=rows,
        ledger_type=RESEARCH_LEDGER,
        filename=filename,
        source="reparodynamics_phase_3b_shadow_scan",
        preview_only=False,
        confirmed=confirmed,
        dedupe=dedupe,
        storage=storage,
        audit_action=REPARODYNAMICS_IMPORT_ACTION,
        audit_extra=f"run_id={run_id}; " if run_id else "",
    )
