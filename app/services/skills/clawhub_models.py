# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 17 — ClawHub marketplace models (remote catalog + local install manifest)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SkillSource(str, Enum):
    BUILTIN = "builtin"
    LOCAL = "local"
    CLAWHUB = "clawhub"


class SkillStatus(str, Enum):
    INSTALLED = "installed"
    OUTDATED = "outdated"
    DISABLED = "disabled"
    BROKEN = "broken"


@dataclass
class ClawHubSkillInfo:
    """Remote skill metadata from ClawHub (best-effort mapping).

    Phase 75 added ``category`` (single-axis filter for the marketplace UI),
    ``readme_url`` / ``changelog_url`` (skill detail modal), and
    ``skill_dependencies`` / ``permissions`` (cross-skill deps + sandbox gate).
    All new fields default to safe empty values so a registry that doesn't
    populate them keeps round-tripping cleanly.
    """

    name: str
    version: str
    description: str
    author: str
    publisher: str
    tags: list[str]
    downloads: int
    rating: float
    updated_at: datetime
    signature: str | None = None
    manifest_url: str = ""
    archive_url: str = ""
    category: str = ""
    readme_url: str = ""
    changelog_url: str = ""
    skill_dependencies: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "publisher": self.publisher,
            "tags": self.tags,
            "downloads": self.downloads,
            "rating": self.rating,
            "updated_at": self.updated_at.isoformat(),
            "signature": self.signature,
            "manifest_url": self.manifest_url,
            "archive_url": self.archive_url,
            "category": self.category,
            "readme_url": self.readme_url,
            "changelog_url": self.changelog_url,
            "skill_dependencies": list(self.skill_dependencies),
            "permissions": list(self.permissions),
        }


@dataclass
class InstalledSkill:
    """Local installed skill record (persisted in installed.yaml).

    Phase 75 added ``available_version`` + ``update_checked_at`` (so the
    background SkillUpdateChecker can stamp newer versions without forcing a
    re-install) and ``category`` (carried through from the remote record so
    the UI doesn't need to re-fetch metadata for already-installed skills).
    All new fields default to safe values; old ``installed.yaml`` rows
    written before 75 round-trip cleanly through ``row_to_installed_skill``.
    """

    name: str
    version: str
    source: SkillSource
    source_url: str | None = None
    installed_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    status: SkillStatus = SkillStatus.INSTALLED
    pinned_version: str | None = None
    publisher: str | None = None
    available_version: str | None = None
    update_checked_at: datetime | None = None
    category: str = ""

    def to_row(self) -> dict[str, Any]:
        """Serialize for YAML manifest round-trip."""
        return {
            "name": self.name,
            "version": self.version,
            "source": self.source.value,
            "source_url": self.source_url,
            "installed_at": self.installed_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "pinned_version": self.pinned_version,
            "publisher": self.publisher,
            "available_version": self.available_version,
            "update_checked_at": (
                self.update_checked_at.isoformat() if self.update_checked_at else None
            ),
            "category": self.category,
        }

    def to_dict(self) -> dict[str, Any]:
        """API-friendly subset."""
        return {
            "name": self.name,
            "version": self.version,
            "source": self.source.value,
            "installed_at": self.installed_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status.value,
            "pinned_version": self.pinned_version,
            "publisher": self.publisher,
            "source_url": self.source_url,
            "available_version": self.available_version,
            "update_checked_at": (
                self.update_checked_at.isoformat() if self.update_checked_at else None
            ),
            "category": self.category,
            "update_available": bool(
                self.available_version
                and self.available_version != self.version
            ),
        }


def row_to_installed_skill(row: dict[str, Any]) -> InstalledSkill:
    src = SkillSource((row.get("source") or "local").strip())
    stat = SkillStatus((row.get("status") or "installed").strip())
    ia = row.get("installed_at")
    ua = row.get("updated_at")
    uca = row.get("update_checked_at")
    return InstalledSkill(
        name=str(row["name"]).strip(),
        version=str(row.get("version", "0.0.0")).strip(),
        source=src,
        source_url=(str(row["source_url"]).strip() if row.get("source_url") else None),
        installed_at=datetime.fromisoformat(ia) if isinstance(ia, str) else datetime.utcnow(),
        updated_at=datetime.fromisoformat(ua) if isinstance(ua, str) else datetime.utcnow(),
        status=stat,
        pinned_version=(str(row["pinned_version"]).strip() if row.get("pinned_version") else None),
        publisher=(str(row["publisher"]).strip() if row.get("publisher") else None),
        available_version=(
            str(row["available_version"]).strip() if row.get("available_version") else None
        ),
        update_checked_at=(
            datetime.fromisoformat(uca) if isinstance(uca, str) and uca else None
        ),
        category=(str(row["category"]).strip() if row.get("category") else ""),
    )


__all__ = [
    "ClawHubSkillInfo",
    "InstalledSkill",
    "SkillSource",
    "SkillStatus",
    "row_to_installed_skill",
]
