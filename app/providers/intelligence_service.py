# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from app.providers.provider_registry import PROVIDER_IDS
from app.providers.provider_sessions import probe_provider_session
from app.runtime.runtime_state import ensure_operator_context_schema, load_runtime_state, save_runtime_state, utc_now_iso

if TYPE_CHECKING:
    from app.core.config import Settings


def scan_providers_inventory(*, settings: Settings | None = None, persist: bool = True) -> dict[str, Any]:
    """Run CLI probes for all known providers and optionally persist to ``aethos.json``."""
    from app.core.config import get_settings

    s = settings or get_settings()
    timeout = float(getattr(s, "aethos_provider_cli_timeout_sec", 20) or 20)
    providers: dict[str, Any] = {}
    for pid in PROVIDER_IDS:
        providers[pid] = probe_provider_session(pid, timeout_sec=timeout)
    inv = {
        "providers": providers,
        "last_scanned_at": utc_now_iso(),
        "privacy": {"scanned": True, "redacted_cli_previews": True},
    }
    if persist:
        st = load_runtime_state()
        ensure_operator_context_schema(st)
        st["provider_inventory"] = inv
        save_runtime_state(st)
    return inv
