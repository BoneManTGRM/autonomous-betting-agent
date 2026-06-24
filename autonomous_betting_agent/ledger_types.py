"""Ledger separation helpers for local-first ABA proof storage.

These helpers keep official proof, research, quarantine, learning-only, and
client-facing rows separated. They intentionally avoid hype and only mark a row
as official when the minimum timestamp/proof/audit requirements are present.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

OFFICIAL_LEDGER = "official"
RESEARCH_LEDGER = "research"
ALL_HIGH_CONFIDENCE_LEDGER = "all_high_confidence"
QUARANTINE_LEDGER = "quarantine"
LEARNING_ONLY_LEDGER = "learning_only"
CLIENT_LEDGER = "client"

LEDGER_TYPES = {
    OFFICIAL_LEDGER,
    RESEARCH_LEDGER,
    ALL_HIGH_CONFIDENCE_LEDGER,
    QUARANTINE_LEDGER,
    LEARNING_ONLY_LEDGER,
    CLIENT_LEDGER,
}

_BAD_STATUS = {"fail", "failed", "quarantine", "review", "blocked", "bad"}
_RESEARCH_FLAGS = {"research", "test", "testing", "learning", "learning_only", "backfill"}
_OFFICIAL_FLAGS = {"official", "official_ev", "+ev", "proof", "client"}


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _lower(value: Any) -> str:
    return _text(value).lower()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return _lower(value) in {"1", "true", "yes", "y", "official", "locked"}


def parse_dt(value: Any) -> datetime | None:
    """Parse common timestamp strings into timezone-aware UTC datetimes."""
    raw = _text(value)
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def has_required_proof_fields(row: Mapping[str, Any]) -> bool:
    return bool(_text(row.get("proof_id")) and _text(row.get("locked_at_utc")) and _text(row.get("event_start_time")))


def is_future_locked(row: Mapping[str, Any]) -> bool:
    locked_at = parse_dt(row.get("locked_at_utc"))
    event_start = parse_dt(row.get("event_start_time") or row.get("commence_time"))
    if not locked_at or not event_start:
        return False
    return locked_at < event_start


def has_clean_audit(row: Mapping[str, Any]) -> bool:
    audit_status = _lower(row.get("odds_audit_status") or row.get("audit_status"))
    if audit_status in _BAD_STATUS:
        return False
    ledger_hint = _lower(row.get("ledger_type") or row.get("proof_type") or row.get("row_type"))
    if ledger_hint in {QUARANTINE_LEDGER, "review_only", "review"}:
        return False
    return True


def is_research_or_learning(row: Mapping[str, Any]) -> bool:
    values = {
        _lower(row.get("ledger_type")),
        _lower(row.get("proof_type")),
        _lower(row.get("row_type")),
        _lower(row.get("source_type")),
    }
    if values & _RESEARCH_FLAGS:
        return True
    return _truthy(row.get("research_only")) or _truthy(row.get("learning_only")) or _truthy(row.get("backfill"))


def can_be_official(row: Mapping[str, Any]) -> bool:
    """Return True only when a row is safe to count as official forward proof."""
    return (
        has_required_proof_fields(row)
        and is_future_locked(row)
        and has_clean_audit(row)
        and not is_research_or_learning(row)
    )


def classify_ledger_type(row: Mapping[str, Any]) -> str:
    """Classify a row into the safest ledger bucket.

    Explicit quarantine/research/learning hints take priority over official hints.
    Official is only returned when forward-proof requirements pass.
    """
    explicit = _lower(row.get("ledger_type") or row.get("proof_type") or row.get("row_type"))
    audit_status = _lower(row.get("odds_audit_status") or row.get("audit_status"))

    if explicit in {QUARANTINE_LEDGER, "review", "review_only"} or audit_status in _BAD_STATUS:
        return QUARANTINE_LEDGER
    if explicit in {LEARNING_ONLY_LEDGER, "learning", "backfill"} or _truthy(row.get("learning_only")):
        return LEARNING_ONLY_LEDGER
    if explicit in {ALL_HIGH_CONFIDENCE_LEDGER, "all_high_confidence", "high_confidence_test"}:
        return ALL_HIGH_CONFIDENCE_LEDGER
    if explicit in {RESEARCH_LEDGER, "test", "testing"} or is_research_or_learning(row):
        return RESEARCH_LEDGER
    if explicit in {CLIENT_LEDGER, "client_facing"} and can_be_official(row):
        return CLIENT_LEDGER
    if explicit in _OFFICIAL_FLAGS or _truthy(row.get("official")):
        return OFFICIAL_LEDGER if can_be_official(row) else RESEARCH_LEDGER
    return OFFICIAL_LEDGER if can_be_official(row) else RESEARCH_LEDGER


def public_metric_allowed(row: Mapping[str, Any]) -> bool:
    """Return True when a row can be counted in public proof metrics."""
    return classify_ledger_type(row) in {OFFICIAL_LEDGER, CLIENT_LEDGER} and can_be_official(row)
