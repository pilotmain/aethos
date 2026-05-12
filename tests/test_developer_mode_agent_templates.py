# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Developer workspace: custom agents default to Base Operator, not legal templates."""

from __future__ import annotations

import pytest

from app.core.config import get_settings
from app.services.custom_agent_parser import (
    explicit_regulated_domain_request,
    parse_custom_agent_from_prompt,
)


@pytest.fixture
def dev_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "developer")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def reg_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEXA_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("NEXA_WORKSPACE_MODE", "regulated")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_chief_operator_is_base_operator_in_developer_mode(dev_env) -> None:
    spec = parse_custom_agent_from_prompt(
        "create a custom agent called @chief-operator. It coordinates runtime tools and missions."
    )
    assert spec is not None
    assert spec.safety_level == "standard"
    assert "Base Operator" in spec.role
    assert "Legal research" not in spec.role
    assert "contract review" not in spec.role.lower()
    assert any("sessions_spawn" in (s or "").lower() for s in spec.skills)


def test_explicit_legal_still_regulated_in_developer_mode(dev_env) -> None:
    spec = parse_custom_agent_from_prompt(
        "create a custom agent called @legal-reviewer. It should review contracts for legal risk."
    )
    assert spec is not None
    assert spec.safety_level == "regulated"
    assert "legal" in spec.role.lower() or "regulated" in spec.role.lower()


def test_regulated_workspace_keeps_broad_contract_hint(reg_env) -> None:
    """Legacy heuristic: 'contract' in body still implies regulated when workspace is regulated."""
    spec = parse_custom_agent_from_prompt(
        "create a custom agent called @corp-analyst. It should analyze customer contracts for our sales team."
    )
    assert spec is not None
    assert spec.safety_level == "regulated"


def test_explicit_regulated_domain_helper() -> None:
    assert explicit_regulated_domain_request("I need a lawyer to review this") is True
    assert explicit_regulated_domain_request("coordinates the runtime and Mission Control") is False
