#!/usr/bin/env python3
"""
Fail if OpenAI / Anthropic SDK imports appear outside ``app/services/providers/``.

Same rule as ``tests/test_no_direct_external_provider_calls.py`` — CI guardrail (Phase 10).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_APP = _REPO_ROOT / "app"
_PROVIDERS = _APP / "services" / "providers"

_FORBIDDEN_LINE_MARKERS = (
    "import openai",
    "from openai ",
    "from openai.",
    "import anthropic",
    "from anthropic ",
    "from anthropic.",
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
            if "app.services.providers.sdk" in line:
                continue
            low = line.lower()
            if any(m in low for m in _FORBIDDEN_LINE_MARKERS):
                bad.append(f"{path.relative_to(_REPO_ROOT)}:{i}:{line.strip()}")
    return bad


def main() -> int:
    bad = scan()
    if bad:
        print("Forbidden provider imports outside app/services/providers:\n" + "\n".join(bad), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
