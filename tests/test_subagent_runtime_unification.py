# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from pathlib import Path


def test_unification_audit_doc_exists() -> None:
    p = Path(__file__).resolve().parents[1] / "docs/SUBAGENT_RUNTIME_UNIFICATION_AUDIT.md"
    assert p.is_file()
    text = p.read_text()
    assert "runtime_agents" in text
    assert "AgentRegistry" in text
