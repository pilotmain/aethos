# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Ensure third-party SDK usage stays confined to ``app/services/providers/``."""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_APP = (_REPO_ROOT / "app").resolve()
_PROVIDERS = (_APP / "services" / "providers").resolve()

# Aligned with scripts/verify_no_direct_providers.py (avoid false positives on ``import OpenAIBackend``).
_VENDOR_IMPORT = re.compile(
    r"""^\s*(?:import\s+(?:openai|anthropic)(?:\s|$|\.)|from\s+(?:openai|anthropic)(?:\s|$|\.))""",
    re.IGNORECASE | re.VERBOSE,
)


def _iter_py_outside_providers() -> list[Path]:
    out: list[Path] = []
    for p in _APP.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        try:
            p.resolve().relative_to(_PROVIDERS)
        except ValueError:
            out.append(p)
        else:
            continue
    return out


def test_no_openai_or_anthropic_imports_outside_providers_package() -> None:
    bad: list[str] = []
    for path in _iter_py_outside_providers():
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), start=1):
            if line.strip().startswith("#"):
                continue
            if "app.services.providers.sdk" in line:
                continue
            if _VENDOR_IMPORT.match(line):
                bad.append(f"{path.relative_to(_REPO_ROOT)}:{i}:{line.strip()}")
    assert not bad, "Forbidden provider imports outside app/services/providers:\n" + "\n".join(bad)
