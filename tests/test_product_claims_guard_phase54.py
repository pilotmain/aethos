# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

import re
from pathlib import Path

_FORBIDDEN = re.compile(
    r"\bSOC2 compliant\b|\bguaranteed secure\b|\bfully autonomous without supervision\b|\breplaces your whole team\b",
    re.IGNORECASE,
)


def test_docs_skip_unqualified_high_risk_claims() -> None:
    root = Path(__file__).resolve().parents[1]
    for path in (root / "docs").glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if "aspiration" in text.lower() or "roadmap" in path.name.lower():
            continue
        assert not _FORBIDDEN.search(text), path.name
