#!/usr/bin/env python3
"""
Fail if OpenAI / Anthropic SDK imports appear outside ``app/services/providers/``.

Same rule as CI guardrails (Phase 10 / 16) — complements import-linter + AST tests.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_APP = _REPO_ROOT / "app"
_PROVIDERS = _APP / "services" / "providers"

# Match real SDK package imports only (not ``import OpenAIBackend`` / ``anthropic_backend`` paths).
_VENDOR_IMPORT = re.compile(
    r"""^\s*(?:import\s+(?:openai|anthropic)(?:\s|$|\.)|from\s+(?:openai|anthropic)(?:\s|$|\.))""",
    re.IGNORECASE | re.VERBOSE,
)


def scan() -> list[str]:
    bad: list[str] = []
    for path in _APP.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            path.resolve().relative_to(_PROVIDERS.resolve())
        except ValueError:
            pass
        else:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), start=1):
            if line.strip().startswith("#"):
                continue
            if _VENDOR_IMPORT.match(line):
                bad.append(f"{path.relative_to(_REPO_ROOT)}:{i}:{line.strip()}")
    return bad


def main() -> int:
    bad = scan()
    if bad:
        print(
            "CRITICAL: ARCHITECTURE VIOLATION — forbidden vendor SDK imports outside "
            "app/services/providers/:\n\n"
            + "\n".join(bad),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
