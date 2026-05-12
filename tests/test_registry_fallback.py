# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Unit tests for bundled marketplace fallback catalog helpers."""

from __future__ import annotations

from types import SimpleNamespace

from app.core.config import REPO_ROOT
from app.services.skills.registry_fallback import (
    filter_skill_dicts,
    merged_fallback_skill_dicts,
    sort_by_downloads,
)


def test_merged_fallback_includes_builtin_and_file() -> None:
    s = SimpleNamespace(
        nexa_clawhub_fallback_catalog_path=str(
            REPO_ROOT / "data" / "aethos_marketplace" / "fallback_skills.json"
        ),
    )
    rows = merged_fallback_skill_dicts(s)
    names = {str(r.get("name", "")).lower() for r in rows}
    assert "github" in names
    assert "telegram" in names


def test_filter_skill_dicts_category() -> None:
    rows = [
        {"name": "a", "category": "devops", "description": "", "tags": []},
        {"name": "b", "category": "data", "description": "", "tags": []},
    ]
    out = filter_skill_dicts(rows, query="", category="data", limit=10)
    assert len(out) == 1 and out[0]["name"] == "b"


def test_sort_by_downloads() -> None:
    rows = [{"name": "low", "downloads": 1}, {"name": "high", "downloads": 99}]
    s = sort_by_downloads(rows)
    assert s[0]["name"] == "high"
