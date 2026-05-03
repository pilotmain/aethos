"""Hash chain helpers for append-only ledger."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def hash_record(previous_hash: str, event_body: dict[str, Any]) -> str:
    blob = (previous_hash + ":").encode("utf-8") + canonical_json_bytes(event_body)
    return hashlib.sha256(blob).hexdigest()


__all__ = ["canonical_json_bytes", "hash_record"]
