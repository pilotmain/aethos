# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Select a registered OpsProvider by key (`Project.provider_key` or env fallback for legacy).
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.ops.providers.base import OpsProvider

# Lazy to keep imports light for tests
_PROVIDERS: dict[str, type["OpsProvider"]] = {}


def _load_providers() -> None:
    if _PROVIDERS:
        return
    from app.services.ops.providers.local_docker import LocalDockerProvider
    from app.services.ops.providers.railway import RailwayProvider

    _PROVIDERS["railway"] = RailwayProvider
    _PROVIDERS["local_docker"] = LocalDockerProvider
    # Alias for `Project.provider_key` / env default
    _PROVIDERS["local"] = LocalDockerProvider
    _PROVIDERS["docker"] = LocalDockerProvider


def get_provider(name: str | None) -> "OpsProvider | None":
    n = (name or "").strip().lower()
    if not n:
        n = (os.environ.get("NEXA_OPS_PROVIDER", "") or "local").strip().lower()
    _load_providers()
    if n in ("", "default"):
        n = "local"
    cls = _PROVIDERS.get(n)
    if cls is None:
        return None
    return cls()


def list_provider_names() -> list[str]:
    _load_providers()
    # Dedupe class ids
    return sorted(_PROVIDERS.keys())


def normalize_provider_key(key: str | None) -> str:
    return (key or "local").strip().lower() or "local"
