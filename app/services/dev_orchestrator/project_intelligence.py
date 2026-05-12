# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ProjectProfile:
    project_key: str | None
    repo_path: str | None
    exists: bool
    is_git_repo: bool
    dirty: bool
    project_types: list[str] = field(default_factory=list)
    signals: list[str] = field(default_factory=list)
    recommended_tools: list[str] = field(default_factory=list)
    recommended_mode: str = "autonomous_cli"


def recommend_tools(project_types: list[str], signals: list[str]) -> list[str]:  # noqa: ARG001
    tools: list[str] = []

    if "jetbrains" in project_types:
        if "java" in project_types:
            tools.append("intellij")
        elif "python" in project_types:
            tools.append("pycharm")
        else:
            tools.append("intellij")

    if "mobile" in project_types:
        tools.append("android_studio")

    if "vscode" in project_types or "node" in project_types:
        tools.append("vscode")

    if "python" in project_types and "pycharm" not in tools:
        tools.append("pycharm")

    tools.append("aider")
    tools.append("manual")

    deduped: list[str] = []
    for t in tools:
        if t not in deduped:
            deduped.append(t)

    return deduped


def detect_project_profile(project: Any) -> ProjectProfile:
    if project is None:
        return ProjectProfile(
            project_key=None,
            repo_path=None,
            exists=False,
            is_git_repo=False,
            dirty=False,
            project_types=[],
            signals=[],
            recommended_tools=["manual"],
            recommended_mode="manual_review",
        )

    raw = (getattr(project, "repo_path", None) or "").strip()
    if not raw:
        return ProjectProfile(
            project_key=getattr(project, "key", None),
            repo_path=None,
            exists=False,
            is_git_repo=False,
            dirty=False,
            project_types=[],
            signals=[],
            recommended_tools=["manual"],
            recommended_mode="manual_review",
        )

    repo_path = Path(raw).expanduser()

    if not repo_path.exists():
        return ProjectProfile(
            project_key=getattr(project, "key", None),
            repo_path=str(repo_path),
            exists=False,
            is_git_repo=False,
            dirty=False,
            project_types=[],
            signals=[],
            recommended_tools=["manual"],
            recommended_mode="manual_review",
        )

    signals: list[str] = []
    project_types: list[str] = []

    def has(name: str) -> bool:
        return (repo_path / name).exists()

    if has("package.json"):
        signals.append("package.json")
        project_types.append("node")

    if has("requirements.txt") or has("pyproject.toml"):
        signals.append("python config")
        project_types.append("python")

    if has("pom.xml") or has("build.gradle") or has("settings.gradle"):
        signals.append("java config")
        project_types.append("java")

    if has("Dockerfile") or has("docker-compose.yml") or has("compose.yaml"):
        signals.append("docker config")
        project_types.append("docker")

    if has(".idea"):
        signals.append(".idea")
        project_types.append("jetbrains")

    if has(".vscode"):
        signals.append(".vscode")
        project_types.append("vscode")

    if has("ios") or has("android"):
        signals.append("mobile folders")
        project_types.append("mobile")

    is_git = (repo_path / ".git").exists() or (repo_path / ".git").is_file()

    dirty = False
    if is_git:
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            dirty = bool((result.stdout or "").strip())
        except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
            dirty = False

    recommended_tools = recommend_tools(project_types, signals)

    return ProjectProfile(
        project_key=getattr(project, "key", None),
        repo_path=str(repo_path.resolve()),
        exists=True,
        is_git_repo=is_git,
        dirty=dirty,
        project_types=sorted(set(project_types)),
        signals=signals,
        recommended_tools=recommended_tools,
        recommended_mode="manual_review" if dirty else "autonomous_cli",
    )
