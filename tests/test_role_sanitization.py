# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""sanitize_agent_roles.py heuristics (legal/read-only template cleanup)."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_script():
    root = Path(__file__).resolve().parent.parent
    path = root / "scripts" / "sanitize_agent_roles.py"
    spec = importlib.util.spec_from_file_location("sanitize_agent_roles", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_needs_sanitize_detects_markers() -> None:
    sar = _load_script()
    assert sar.needs_sanitize("I cannot provide legal advice.") is True
    assert sar.needs_sanitize("I am read-only.") is True
    assert sar.needs_sanitize("Plain helpful assistant.") is False


def test_base_operator_template_importable() -> None:
    from app.services.custom_agents import BASE_OPERATOR_TEMPLATE

    assert "Base Operator" in BASE_OPERATOR_TEMPLATE
    assert len(BASE_OPERATOR_TEMPLATE) > 80
