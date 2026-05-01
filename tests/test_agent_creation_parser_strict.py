"""Custom agent creation must not mint handles from Role:/Skills: labels."""

from __future__ import annotations

from app.services.custom_agent_parser import (
    extract_explicit_agent_creation_handles,
    is_valid_user_agent_handle,
    parse_custom_agent_from_prompt,
)


def test_rejects_section_label_handles() -> None:
    assert is_valid_user_agent_handle("role") is False
    assert is_valid_user_agent_handle("skills") is False
    assert is_valid_user_agent_handle("guardrails") is False


def test_parse_post_creation_spec_returns_none() -> None:
    blob = """
Created custom agent @boss.

Role:
Base Operator / System Orchestrator

Skills:
- sessions_spawn

Guardrails:
- bounded missions only

Use it by saying:
@boss review this contract
""".strip()
    assert parse_custom_agent_from_prompt(blob) is None


def test_explicit_agent_list_extracts_handles() -> None:
    text = """
Create these agents:
@boss
@researcher-pro
@analyst-pro
@qa-pro
""".strip()
    h = extract_explicit_agent_creation_handles(text)
    assert h == ["boss", "researcher-pro", "analyst-pro", "qa-pro"]
