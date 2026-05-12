# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 28 — documentation must not advertise removed HTTP paths."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# Exact obsolete bullets only — prose may say “replaces …/summary” without recommending the old route.
_FORBIDDEN = (
    "GET /api/v1/mission-control/summary",
    "`GET /api/v1/mission-control/summary`",
    "`GET /api/v1/memory` — `PUT /api/v1/memory/preferences`",
)


def test_docs_do_not_reference_removed_summary_or_legacy_memory() -> None:
    bad: list[str] = []
    for p in sorted(DOCS.rglob("*.md")):
        if p.name == "API_CONTRACT.md":
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for needle in _FORBIDDEN:
            if needle in text:
                bad.append(f"{p.relative_to(ROOT)}: {needle!r}")
    assert not bad, "Update docs to use /mission-control/state and /web/memory:\n" + "\n".join(bad)


def test_api_contract_doc_exists() -> None:
    assert (ROOT / "docs" / "API_CONTRACT.md").is_file()
