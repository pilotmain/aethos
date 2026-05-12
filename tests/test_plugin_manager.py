# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Tests for optional ``aethos_pro`` plugin loader (OSS repo has no commercial package)."""

from __future__ import annotations

from aethos_core.plugin_manager import PluginManager


def test_is_pro_available_false_without_wheel() -> None:
    assert PluginManager.is_pro_available() is False


def test_load_proprietary_returns_fallback() -> None:
    sentinel = object()
    assert PluginManager.load_proprietary("nonexistent_xyz", fallback=sentinel) is sentinel


def test_load_proprietary_invalid_name_returns_fallback() -> None:
    assert PluginManager.load_proprietary("bad.name", fallback=1) == 1
