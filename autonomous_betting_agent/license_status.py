"""Manual local license tracking helpers.

This module intentionally does not import Stripe or process payments. It stores
simple local records for operator tracking only.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

LICENSE_STATUSES = {"active", "trial", "inactive", "expired"}
DEFAULT_LICENSE_PATH = Path("data/local_license_status.csv")


@dataclass(frozen=True)
class LicenseRecord:
    client_name: str
    client_status: str = "trial"
    subscription_tier: str = "private_beta"
    manual_payment_status: str = "manual"
    renewal_date: str = ""
    notes: str = ""
    future_stripe_ready: bool = False


def normalize_client_status(value: Any) -> str:
    status = str(value or "trial").strip().lower()
    return status if status in LICENSE_STATUSES else "inactive"


def make_license_record(
    client_name: str,
    client_status: str = "trial",
    subscription_tier: str = "private_beta",
    manual_payment_status: str = "manual",
    renewal_date: str = "",
    notes: str = "",
    future_stripe_ready: bool = False,
) -> LicenseRecord:
    return LicenseRecord(
        client_name=str(client_name or "").strip(),
        client_status=normalize_client_status(client_status),
        subscription_tier=str(subscription_tier or "private_beta").strip(),
        manual_payment_status=str(manual_payment_status or "manual").strip(),
        renewal_date=str(renewal_date or "").strip(),
        notes=str(notes or "").strip(),
        future_stripe_ready=bool(future_stripe_ready),
    )


def load_license_records(path: str | Path = DEFAULT_LICENSE_PATH) -> list[LicenseRecord]:
    src = Path(path)
    if not src.exists() or src.stat().st_size == 0:
        return []
    with src.open("r", newline="", encoding="utf-8") as fh:
        return [
            make_license_record(
                row.get("client_name", ""),
                row.get("client_status", "trial"),
                row.get("subscription_tier", "private_beta"),
                row.get("manual_payment_status", "manual"),
                row.get("renewal_date", ""),
                row.get("notes", ""),
                str(row.get("future_stripe_ready", "false")).lower() in {"1", "true", "yes"},
            )
            for row in csv.DictReader(fh)
        ]


def save_license_records(records: Iterable[LicenseRecord], path: str | Path = DEFAULT_LICENSE_PATH) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = [asdict(record) for record in records]
    fieldnames = ["client_name", "client_status", "subscription_tier", "manual_payment_status", "renewal_date", "notes", "future_stripe_ready"]
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return out


def upsert_license_record(record: LicenseRecord, path: str | Path = DEFAULT_LICENSE_PATH) -> list[LicenseRecord]:
    records = load_license_records(path)
    updated: list[LicenseRecord] = []
    replaced = False
    for existing in records:
        if existing.client_name.lower() == record.client_name.lower():
            updated.append(record)
            replaced = True
        else:
            updated.append(existing)
    if not replaced:
        updated.append(record)
    save_license_records(updated, path)
    return updated
