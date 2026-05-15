# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 49 — natural multi-agent parse, QA path scan helpers."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from app.services.qa_agent.file_analysis import run_qa_file_analysis
from app.services.sub_agent_natural_creation import parse_natural_sub_agent_specs


def test_parse_three_agents_role_for_syntax() -> None:
    text = (
        "create three agents: backend_agent for API development, "
        "frontend_agent for UI, and security_agent for code review"
    )
    specs = parse_natural_sub_agent_specs(text)
    names = [s[0] for s in specs]
    assert "backend_agent" in names and "frontend_agent" in names and "security_agent" in names
    dom = {s[0]: s[1] for s in specs}
    assert dom["backend_agent"] == "backend"
    assert dom["frontend_agent"] == "frontend"
    assert dom["security_agent"] == "security"


def test_qa_file_analysis_respects_workspace(tmp_path: Path) -> None:
    p = tmp_path / "sample.py"
    p.write_text("api_key='secret'\nimport subprocess\n", encoding="utf-8")

    class _S:
        host_executor_work_root = str(tmp_path)
        nexa_workspace_root = str(tmp_path)

    with patch("app.services.qa_agent.file_analysis.get_settings", return_value=_S()):
        out = run_qa_file_analysis(f"please analyze {p}")
    assert "api_key" in out or "hardcoded" in out.lower()
    assert "subprocess" in out.lower()


def test_fsmonitor_watch_registers(tmp_path: Path) -> None:
    from app.services import fsmonitor as fm

    fm.stop_all()
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    seen: list[str] = []

    def cb(fp: str) -> None:
        seen.append(fp)

    wid = fm.watch(str(tmp_path), "*.py", cb, duration_seconds=60.0)
    assert wid
    fm.stop_all()


def test_qa_scan_requires_resolvable_path_string() -> None:
    from app.services.qa_agent.file_analysis import has_absolute_path_for_qa_scan

    assert has_absolute_path_for_qa_scan("analyze /tmp/x.py") is True
    assert has_absolute_path_for_qa_scan("review it") is False
