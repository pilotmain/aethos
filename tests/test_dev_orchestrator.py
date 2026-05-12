# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from app.services.dev_orchestrator.dev_decision import decide_dev_execution
from app.services.dev_orchestrator.orchestrator import build_dev_execution_plan
from app.services.dev_orchestrator.project_intelligence import detect_project_profile
from app.services.dev_orchestrator.retry_advisor import advise_retry
from app.services.dev_orchestrator.task_classifier import classify_dev_task


def _proj(**kwargs):
    return SimpleNamespace(
        key=kwargs.get("key", "t"),
        display_name=kwargs.get("display_name", "T"),
        repo_path=kwargs.get("repo_path"),
        preferred_dev_tool=kwargs.get("preferred_dev_tool"),
        dev_execution_mode=kwargs.get("dev_execution_mode"),
    )


def test_detect_python_repo(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname=x\n", encoding="utf-8")
    (tmp_path / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.local"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init", "--no-gpg-sign"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    p = _proj(repo_path=str(tmp_path))
    prof = detect_project_profile(p)
    assert prof.exists
    assert prof.is_git_repo
    assert "python" in prof.project_types
    assert "docker" in prof.project_types
    assert prof.dirty is False


def test_detect_node_repo(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.local"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init", "--no-gpg-sign"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    prof = detect_project_profile(_proj(repo_path=str(tmp_path)))
    assert "node" in prof.project_types


def test_detect_dirty_tree(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init", "--no-gpg-sign"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    (tmp_path / "dirty.txt").write_text("y", encoding="utf-8")
    prof = detect_project_profile(_proj(repo_path=str(tmp_path)))
    assert prof.dirty is True


def test_classify_docs_low_risk() -> None:
    c = classify_dev_task("add a README note for Nexa")
    assert c.task_type == "small_safe_change"
    assert c.risk_level == "low"
    assert c.preferred_mode == "autonomous_cli"


def test_classify_infra_high_risk() -> None:
    c = classify_dev_task("change database auth flow in Nexa")
    assert c.preferred_mode == "ide_handoff"
    assert c.risk_level == "high"


def test_decide_uses_project_preferred_tool(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.local"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    (tmp_path / "pyproject.toml").write_text("[project]\nname=x\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init", "--no-gpg-sign"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    p = _proj(repo_path=str(tmp_path), preferred_dev_tool="vscode", dev_execution_mode="ide_handoff")
    prof = detect_project_profile(p)
    task = classify_dev_task("small tweak")
    d = decide_dev_execution(p, prof, task)
    assert d.tool_key == "vscode"
    assert d.mode == "ide_handoff"


def test_decide_blocks_missing_repo() -> None:
    p = _proj(repo_path="/no/such/path/for/nexa-test")
    prof = detect_project_profile(p)
    task = classify_dev_task("anything")
    d = decide_dev_execution(p, prof, task)
    assert d.mode == "manual_review"
    assert d.tool_key == "manual"


def test_decide_blocks_non_git(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hi", encoding="utf-8")
    p = _proj(repo_path=str(tmp_path))
    prof = detect_project_profile(p)
    task = classify_dev_task("x")
    d = decide_dev_execution(p, prof, task)
    assert d.mode == "manual_review"
    assert "git" in d.reason.lower()


def test_decide_switches_non_aider_autonomous_to_ide_handoff(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.local"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init", "--no-gpg-sign"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    p = _proj(
        repo_path=str(tmp_path),
        preferred_dev_tool="vscode",
        dev_execution_mode="autonomous_cli",
    )
    prof = detect_project_profile(p)
    task = classify_dev_task("typo in comment")
    d = decide_dev_execution(p, prof, task)
    assert d.mode == "ide_handoff"
    assert any("autonomous CLI" in w for w in d.warnings)


def test_execution_plan_contains_fields(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "i", "--no-gpg-sign"],
        cwd=str(tmp_path),
        check=True,
        capture_output=True,
    )
    p = _proj(repo_path=str(tmp_path), key="nexa", display_name="Nexa")
    out = build_dev_execution_plan(p, "update readme")
    msg = out["message"]
    assert "Development execution plan" in msg
    assert "Tool:" in msg or "Execution:" in msg
    frag = out["payload_fragment"]
    assert frag["execution_decision"]["tool_key"]
    assert frag["execution_decision"]["mode"]


def test_worker_payload_fallback_logic() -> None:
    """Mirrors dev_agent_executor: decision overrides top-level when present."""
    pl = {"dev_execution_mode": "autonomous_cli", "preferred_dev_tool": "vscode"}
    ed = pl.get("execution_decision") or {}
    mode = (ed.get("mode") or pl.get("dev_execution_mode") or "autonomous_cli").strip()
    tool = (ed.get("tool_key") or pl.get("preferred_dev_tool") or "aider").strip()
    assert mode == "autonomous_cli"
    assert tool == "vscode"
    pl2 = {
        **pl,
        "execution_decision": {"mode": "ide_handoff", "tool_key": "intellij"},
    }
    ed2 = pl2.get("execution_decision") or {}
    assert (ed2.get("mode") or pl2.get("dev_execution_mode")) == "ide_handoff"
    assert (ed2.get("tool_key") or pl2.get("preferred_dev_tool")) == "intellij"


def test_retry_advice_dirty_worktree() -> None:
    job = SimpleNamespace(failure_stage="dirty_worktree", error_message="dirty", id=9)
    assert "clean" in advise_retry(job).lower()


def test_retry_advice_default() -> None:
    job = SimpleNamespace(failure_stage=None, error_message="unknown", id=3)
    assert "logs" in advise_retry(job).lower()
