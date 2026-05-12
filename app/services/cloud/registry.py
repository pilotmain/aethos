# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Universal cloud provider registry — declarative CLI shapes + NL detection.

Providers load from merged YAML configuration (see :mod:`app.services.cloud.loader`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ProviderCapability(str, Enum):
    DEPLOY = "deploy"
    LOGS = "logs"
    STATUS = "status"
    DESTROY = "destroy"
    LIST = "list"
    ENV = "env"
    PLAN = "plan"


@dataclass
class CloudProvider:
    """Definition of a cloud provider CLI."""

    name: str
    display_name: str
    cli_package: Optional[str] = None
    install_command: Optional[str] = None
    token_env_var: Optional[str] = None
    project_id_env_var: Optional[str] = None
    capabilities: list[ProviderCapability] = field(default_factory=list)
    detect_patterns: list[str] = field(default_factory=list)
    deploy_command: list[str] = field(default_factory=list)
    logs_command: list[str] = field(default_factory=list)
    status_command: list[str] = field(default_factory=list)
    destroy_command: list[str] = field(default_factory=list)
    list_command: list[str] = field(default_factory=list)
    env_command: list[str] = field(default_factory=list)
    plan_command: list[str] = field(default_factory=list)
    removable_config_file: Optional[str] = None

    @property
    def is_removable_drop_in(self) -> bool:
        """True when this definition can be removed via ``/remove_provider`` (user drop-in file)."""
        return bool(self.removable_config_file)


class CloudProviderRegistry:
    """Registry of supported providers (populated from YAML via :func:`get_provider_registry`)."""

    def __init__(self) -> None:
        self._providers: dict[str, CloudProvider] = {}

    def register(self, provider: CloudProvider) -> None:
        self._providers[provider.name] = provider

    def get(self, name: str) -> CloudProvider | None:
        return self._providers.get((name or "").strip().lower())

    def detect_from_text(self, text: str) -> CloudProvider | None:
        """Prefer the **longest** matching pattern across providers (reduces ambiguity)."""
        t = (text or "").lower()
        if not t.strip():
            return None

        scored: list[tuple[int, CloudProvider]] = []
        for p in self._providers.values():
            pats = sorted({x.lower() for x in (p.detect_patterns or [])}, key=len, reverse=True)
            for pat in pats:
                if len(pat) >= 5:
                    hit = pat in t
                else:
                    hit = bool(re.search(rf"\b{re.escape(pat)}\b", t))
                if hit:
                    scored.append((len(pat), p))
                    break
        if not scored:
            return None
        scored.sort(key=lambda x: -x[0])
        return scored[0][1]

    def list_all(self) -> list[CloudProvider]:
        return sorted(self._providers.values(), key=lambda x: x.display_name.lower())


_registry: CloudProviderRegistry | None = None


def get_provider_registry(*, force_reload: bool = False) -> CloudProviderRegistry:
    """Return the merged cloud provider registry, optionally reloading from disk."""
    global _registry
    if force_reload or _registry is None:
        from app.services.cloud.loader import load_registry_from_config

        _registry = load_registry_from_config()
    return _registry


__all__ = [
    "CloudProvider",
    "CloudProviderRegistry",
    "ProviderCapability",
    "get_provider_registry",
]
