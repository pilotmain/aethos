# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Singleton registry for Phase 11 :class:`~app.services.llm.base.LLMProvider` instances."""

from __future__ import annotations

import logging
from typing import Any

from app.services.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class LLMRegistry:
    """Process-local registry (single-worker assumption matches orchestration docs)."""

    _instance: LLMRegistry | None = None

    def __new__(cls) -> LLMRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers = {}
            cls._instance._default_name: str | None = None
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        # Attributes set in __new__
        pass

    def register(self, name: str, provider: LLMProvider, *, set_default: bool = False) -> None:
        key = name.strip().lower()
        self._providers[key] = provider
        if set_default or self._default_name is None:
            self._default_name = key
        logger.debug("LLM registry: registered %s (default=%s)", key, self._default_name)

    def get_provider(self, name: str | None = None) -> LLMProvider | None:
        key = (name or self._default_name or "").strip().lower()
        if not key:
            return None
        return self._providers.get(key)

    def set_default(self, name: str) -> bool:
        key = name.strip().lower()
        if key not in self._providers:
            return False
        self._default_name = key
        logger.info("Default LLM provider set to %s", key)
        return True

    def list_providers(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for name, prov in sorted(self._providers.items()):
            try:
                info = prov.get_model_info()
                out.append(
                    {
                        "name": name,
                        "model": info.name,
                        "logical_provider": info.provider,
                        "context_length": info.context_length,
                        "supports_tools": info.supports_tools,
                        "is_default": name == self._default_name,
                    }
                )
            except Exception as exc:  # noqa: BLE001
                out.append({"name": name, "model": "unknown", "error": str(exc)})
        return out

    def mark_initialized(self) -> None:
        self._initialized = True

    @property
    def initialized(self) -> bool:
        return bool(self._initialized)


_registry_singleton = LLMRegistry()


def get_llm_registry() -> LLMRegistry:
    return _registry_singleton


def reset_llm_registry_for_tests() -> None:
    """Clear registry between tests."""
    reg = get_llm_registry()
    reg._providers = {}
    reg._default_name = None
    reg._initialized = False
    LLMRegistry._instance = None


__all__ = ["LLMRegistry", "get_llm_registry", "reset_llm_registry_for_tests"]
