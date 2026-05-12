# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 26 — dev_runtime must not depend on swarm or legacy mission_control stacks."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = re.compile(
    r"(^\s*from\s+app\.services\.swarm\b|^\s*import\s+app\.services\.swarm\b|mission_control\.legacy)",
    re.MULTILINE,
)


def test_dev_runtime_package_has_no_forbidden_imports() -> None:
    base = ROOT / "app/services/dev_runtime"
    for path in sorted(base.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if FORBIDDEN.search(text):
            raise AssertionError(f"forbidden import reference in {path.relative_to(ROOT)}")
