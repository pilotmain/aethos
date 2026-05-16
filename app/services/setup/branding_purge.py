# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Branding purge audit rules (Phase 4 Step 11)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

FORBIDDEN_USER_FACING = ("OpenHub", "openhub", "ClawHub", "clawhub")

ALLOWED_PATH_PREFIXES = (
    "docs/OPENCLAW_",
    "tests/test_openclaw_",
    "docs/openclaw_",
    "web/app/mission-control/(shell)/differentiators/",
    "web/lib/navigation.ts",
)

ALLOWED_README_OPENCLAW = re.compile(r"Inspired by OpenClaw", re.I)

SCAN_ROOTS = ("aethos_cli", "web/app", "web/components", "web/lib", "install.sh", "scripts/setup.sh")

NEXA_ALLOWED_IN = (".env.example", "app/core/config.py", "COMPATIBILITY", "legacy", "alias", "NEXA_")


def _path_allowed(rel: str) -> bool:
    if any(rel.startswith(p) for p in ALLOWED_PATH_PREFIXES):
        return True
    if rel == "README.md":
        return True
    return False


def scan_user_facing_branding(*, repo_root: Path | None = None) -> dict[str, Any]:
    root = repo_root or Path.cwd()
    violations: list[dict[str, str]] = []
    for rel_root in SCAN_ROOTS:
        base = root / rel_root
        if base.is_file():
            paths = [base]
        elif base.is_dir():
            paths = list(base.rglob("*"))
        else:
            continue
        for path in paths:
            if not path.is_file() or path.suffix not in (".py", ".ts", ".tsx", ".sh", ".md"):
                continue
            rel = str(path.relative_to(root))
            if _path_allowed(rel):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for term in FORBIDDEN_USER_FACING:
                if term in text:
                    violations.append({"path": rel, "term": term})
            if "OpenClaw" in text or "openclaw" in text:
                if rel != "README.md" or not ALLOWED_README_OPENCLAW.search(text):
                    if "parity" not in rel.lower() and "test_openclaw" not in rel:
                        violations.append({"path": rel, "term": "OpenClaw"})
    return {
        "clean": len(violations) == 0,
        "violations": violations[:50],
        "allowed_openclaw": ["README inspiration line", "docs/OPENCLAW_*", "tests/test_openclaw_*"],
        "allowed_nexa": ["env aliases NEXA_*", "config migration", ".env.example"],
        "user_facing_brand": "AethOS",
    }
