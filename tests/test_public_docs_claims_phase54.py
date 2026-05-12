# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import re
from pathlib import Path


_BLOCKED = re.compile(
    r"\bfully replaces OpenClaw\b|\benterprise certified\b|\bSOC2 compliant\b|\b500k stars\b",
    re.IGNORECASE,
)


def test_public_docs_avoid_absolutist_hype() -> None:
    root = Path(__file__).resolve().parents[1]
    for name in ("MIGRATING_FROM_OPENCLAW.md", "WHY_NEXA.md", "ROADMAP_PUBLIC.md"):
        text = (root / "docs" / name).read_text(encoding="utf-8")
        assert not _BLOCKED.search(text), name
