"""Client profile helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ClientProfile:
    client_id: str = "default"
    name: str = "Default Client"
    mode: str = "balanced"
