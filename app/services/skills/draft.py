# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Draft skills from natural language — installation requires explicit approval."""

from __future__ import annotations

import re
from typing import Any

_SLUG = re.compile(r"[^a-z0-9_-]+")


def slugify(text: str) -> str:
    s = text.strip().lower().replace(" ", "_")
    s = _SLUG.sub("", s)
    return (s[:48] or "draft_skill").strip("_")


def draft_skill_from_prompt(user_text: str) -> dict[str, Any]:
    """Produce a manifest-shaped draft — not installed until validated + approved."""
    tid = slugify(user_text[:80])
    return {
        "id": tid,
        "name": (user_text[:120] or "Draft skill").strip(),
        "description": "Auto-drafted capability — review permissions before enabling.",
        "version": "0.0.0-draft",
        "author": "nexa-draft",
        "permissions": [],
        "entrypoint": "skill.py",
        "privacy_policy": "firewall_required",
        "risk_level": "medium",
        "draft": True,
        "requires_approval": True,
    }


def validate_skill_manifest(manifest: dict[str, Any]) -> tuple[bool, list[str]]:
    errs: list[str] = []
    if not str(manifest.get("id") or "").strip():
        errs.append("missing id")
    if not str(manifest.get("name") or "").strip():
        errs.append("missing name")
    rl = str(manifest.get("risk_level") or "").lower()
    if rl not in ("low", "medium", "high"):
        errs.append("risk_level must be low|medium|high")
    return len(errs) == 0, errs


__all__ = ["draft_skill_from_prompt", "validate_skill_manifest"]
