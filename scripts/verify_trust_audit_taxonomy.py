#!/usr/bin/env python3
"""
Fail CI if trust-shaped audit event strings are inlined outside trust_audit_constants.

Run from repo root: python scripts/verify_trust_audit_taxonomy.py

Allowed: ``event_type=ACCESS_*`` constants, dynamic variables, and definitions in ``trust_audit_constants.py``.
Forbidden: literal ``event_type=\"access.permission...\"`` etc. outside the constants module.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "app"
SKIP_NAMES = frozenset({"trust_audit_constants.py"})
# Matches common trust prefixes when used as quoted string literals (namespace drift guard).
_ILLEGAL_LITERAL = re.compile(
    r'event_type\s*=\s*["\']((?:access\.(permission|host_executor|sensitive)'
    r"|network\.external_send|safety\.enforcement)[^\"']*)[\"']"
)


def main() -> int:
    bad: list[str] = []
    for path in sorted(ROOT.rglob("*.py")):
        if path.name in SKIP_NAMES:
            continue
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if _ILLEGAL_LITERAL.search(line):
                bad.append(f"{path.relative_to(ROOT.parent)}:{i}:{line.strip()}")
    if bad:
        print("Trust audit taxonomy: inline event_type literals found (use trust_audit_constants):\n")
        print("\n".join(bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
