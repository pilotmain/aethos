"""Pick an allowlisted test command for the repo layout."""

from __future__ import annotations

import json
from pathlib import Path


def pick_test_command(repo_root: Path) -> str:
    """Prefer pytest for Python repos, else npm test when package.json has a test script."""
    pkg = repo_root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            scripts = data.get("scripts") or {}
            if isinstance(scripts, dict) and scripts.get("test"):
                return "npm test"
        except (OSError, json.JSONDecodeError):
            pass
    if (
        (repo_root / "pytest.ini").is_file()
        or (repo_root / "pyproject.toml").is_file()
        or (repo_root / "tests").is_dir()
    ):
        return "python -m pytest"
    return "python -m pytest"


__all__ = ["pick_test_command"]
