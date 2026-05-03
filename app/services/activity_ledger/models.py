"""Ledger row shape (serialized to JSON-compatible dict)."""

from __future__ import annotations

from typing import Any, TypedDict


class LedgerEventDict(TypedDict, total=False):
    event_type: str
    actor: str
    resource: str
    payload_summary: dict[str, Any]
    previous_hash: str
    hash: str


__all__ = ["LedgerEventDict"]
