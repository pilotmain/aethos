#!/usr/bin/env python3
"""Add Apache-2.0 SPDX file headers to first-party Python trees (one-time / idempotent)."""

from __future__ import annotations

import sys
from pathlib import Path

HEADER = "# SPDX-License-Identifier: Apache-2.0\n# Copyright (c) 2025 AethOS AI\n\n"
MARKER = "SPDX-License-Identifier"

# Repo-relative directories to scan (exclude vendor trees and venv).
ROOTS = ("app", "scripts", "tests", "aethos_cli", "nexa-ext-pro")


def _skip_path(p: Path) -> bool:
    parts = set(p.parts)
    if "__pycache__" in parts or ".venv" in parts or "node_modules" in parts:
        return True
    return False


def insert_header(text: str) -> str | None:
    if MARKER in text:
        return None
    if text.startswith("#!/"):
        nl = text.find("\n")
        if nl == -1:
            return None
        head = text[: nl + 1]
        rest = text[nl + 1 :]
        if rest.startswith("\n"):
            rest = rest[1:]
        return head + HEADER + rest
    return HEADER + text


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    changed = 0
    scanned = 0
    for name in ROOTS:
        base = root / name
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if _skip_path(path):
                continue
            scanned += 1
            raw = path.read_text(encoding="utf-8")
            new = insert_header(raw)
            if new is not None:
                path.write_text(new, encoding="utf-8", newline="\n")
                changed += 1
    print(f"scanned={scanned} updated={changed}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
