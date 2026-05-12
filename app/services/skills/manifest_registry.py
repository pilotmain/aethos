# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Load packaged skills from data/nexa_skill_packages/ (Phase 53)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT
from app.services.skills.models import SkillMeta

_DEFAULT_DIR = REPO_ROOT / "data" / "nexa_skill_packages"


class SkillPackageRegistry:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or _DEFAULT_DIR

    def list_skills(self) -> list[SkillMeta]:
        out: list[SkillMeta] = []
        if not self.base_dir.is_dir():
            return out
        for man in sorted(self.base_dir.glob("*/manifest.json")):
            try:
                data = json.loads(man.read_text(encoding="utf-8"))
                out.append(self._from_dict(data))
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue
        return out

    @staticmethod
    def _from_dict(data: dict[str, Any]) -> SkillMeta:
        perms = data.get("permissions") or []
        if not isinstance(perms, list):
            perms = []
        rl = str(data.get("risk_level") or "low").lower()
        if rl not in ("low", "medium", "high"):
            rl = "low"
        return SkillMeta(
            id=str(data.get("id") or "unknown"),
            name=str(data.get("name") or data.get("id") or "Skill"),
            description=str(data.get("description") or ""),
            version=str(data.get("version") or "0.0.0"),
            author=str(data.get("author") or "local"),
            permissions=tuple(str(x) for x in perms),
            entrypoint=str(data.get("entrypoint") or "skill.py"),
            privacy_policy=str(data.get("privacy_policy") or "firewall_required"),
            risk_level=rl,  # type: ignore[arg-type]
            extra={k: v for k, v in data.items() if k not in {"id", "name", "description", "version", "author", "permissions", "entrypoint", "privacy_policy", "risk_level"}},
        )


__all__ = ["SkillPackageRegistry"]
