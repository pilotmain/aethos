"""Parse ``skill.yaml`` manifests for the Phase 6 pluggable skill runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class SkillManifest:
    """Normalized manifest fields used by :mod:`app.services.skills.plugin_registry`.

    Phase 75 added ``skill_dependencies`` (a separate channel from the existing
    ``dependencies`` pip-package list, processed by
    :mod:`app.services.skills.dependency_resolver` before install) and
    ``category`` (single-axis filter, mirrors the upstream
    :class:`~app.services.skills.clawhub_models.ClawHubSkillInfo` field). Both
    default to safe empty values so manifests written before 75 keep loading.
    """

    name: str
    version: str
    description: str
    author: str
    tags: list[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    execution_type: str
    entry: str
    handler: str
    dependencies: list[str]
    permissions: list[str]
    source: str
    base_dir: Path
    skill_dependencies: list[str] = field(default_factory=list)
    category: str = ""


def load_skill_manifest(path: Path) -> SkillManifest:
    """Load ``skill.yaml`` (or ``.yml``) from disk."""
    raw_text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(raw_text)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid skill manifest (expected mapping): {path}")
    ex = data.get("execution") or {}
    if not isinstance(ex, dict):
        raise ValueError(f"Invalid execution block in {path}")
    skill_deps_raw = data.get("skill_dependencies")
    skill_deps = (
        [str(d).strip() for d in skill_deps_raw if str(d).strip()]
        if isinstance(skill_deps_raw, list)
        else []
    )
    return SkillManifest(
        name=str(data["name"]).strip(),
        version=str(data.get("version", "0.0.0")).strip(),
        description=str(data.get("description", "")).strip(),
        author=str(data.get("author", "unknown")).strip(),
        tags=list(data.get("tags") or []) if isinstance(data.get("tags"), list) else [],
        input_schema=data.get("input_schema") if isinstance(data.get("input_schema"), dict) else {},
        output_schema=data.get("output_schema") if isinstance(data.get("output_schema"), dict) else {},
        execution_type=str(ex.get("type", "python")).strip().lower(),
        entry=str(ex.get("entry", "")).strip(),
        handler=str(ex.get("handler", "")).strip(),
        dependencies=list(data.get("dependencies") or [])
        if isinstance(data.get("dependencies"), list)
        else [],
        permissions=[str(p).strip().lower() for p in (data.get("permissions") or []) if str(p).strip()]
        if isinstance(data.get("permissions"), list)
        else [],
        source=str(data.get("source") or "local").strip(),
        base_dir=path.resolve().parent,
        skill_dependencies=skill_deps,
        category=str(data.get("category") or "").strip().lower(),
    )


__all__ = ["SkillManifest", "load_skill_manifest"]
