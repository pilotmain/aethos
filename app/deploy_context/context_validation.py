# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Workspace + marker validation for deploy context (Phase 2 Step 4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.deploy_context.errors import WorkspaceValidationError


def workspace_confidence(repo_path: Path) -> dict[str, Any]:
    """Return confidence label + human-readable signals (no network)."""
    p = repo_path.resolve()
    signals: list[str] = []
    if (p / "package.json").is_file():
        signals.append("package.json")
    if (p / "pyproject.toml").is_file():
        signals.append("pyproject.toml")
    if (p / ".git").exists():
        signals.append(".git")
    if (p / ".vercel" / "project.json").is_file():
        signals.append(".vercel/project.json")
    if (p / "vercel.json").is_file():
        signals.append("vercel.json")
    score = len(signals)
    if score >= 4:
        level = "high"
    elif score >= 2:
        level = "medium"
    else:
        level = "low"
    return {"workspace_confidence": level, "signals": signals}


def validate_repo_path(repo_path: str | Path) -> Path:
    raw = Path(str(repo_path).strip()).expanduser()
    if not raw.exists():
        raise WorkspaceValidationError(
            f"I could not find the repository path:\n{raw}",
            suggestions=["Check the path exists.", "Run: aethos projects scan", "Run: aethos projects link <slug> <absolute-path>"],
            details={"repo_path": str(raw)},
        )
    if not raw.is_dir():
        raise WorkspaceValidationError(
            f"The path is not a directory:\n{raw}",
            suggestions=["Point to the project root folder (where package.json or markers live)."],
            details={"repo_path": str(raw)},
        )
    return raw.resolve()


def require_package_json_or_pyproject(repo: Path) -> None:
    if not (repo / "package.json").is_file() and not (repo / "pyproject.toml").is_file():
        raise WorkspaceValidationError(
            "I could not find package.json or pyproject.toml in the selected workspace.",
            suggestions=[
                "Confirm this is the app root (not a parent folder).",
                "Run: aethos projects scan",
                "Link the correct root: aethos projects link <slug> <path-to-root>",
            ],
            details={"repo_path": str(repo)},
        )
