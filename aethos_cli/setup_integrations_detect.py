# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Detect provider/project CLI integrations (Phase 4 Step 4)."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any


def _version(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=8.0)
        if r.returncode == 0:
            return (r.stdout or r.stderr or "").strip().splitlines()[0][:80]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def detect_integrations() -> dict[str, Any]:
    tools = {
        "git": shutil.which("git"),
        "gh": shutil.which("gh"),
        "vercel": shutil.which("vercel"),
        "railway": shutil.which("railway"),
        "fly": shutil.which("fly"),
        "netlify": shutil.which("netlify"),
        "wrangler": shutil.which("wrangler"),
        "docker": shutil.which("docker"),
        "ollama": shutil.which("ollama"),
        "node": shutil.which("node"),
        "python": shutil.which("python3") or shutil.which("python"),
        "npm": shutil.which("npm"),
    }
    versions: dict[str, str | None] = {}
    if tools["git"]:
        versions["git"] = _version(["git", "--version"])
    if tools["gh"]:
        versions["gh"] = _version(["gh", "--version"])
    if tools["docker"]:
        versions["docker"] = _version(["docker", "--version"])
    if tools["ollama"]:
        versions["ollama"] = _version(["ollama", "--version"])
    return {"installed": {k: bool(v) for k, v in tools.items()}, "versions": versions}
