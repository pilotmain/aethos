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
    """Remote skill metadata from ClawHub (best-effort mapping)."""

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
        }


@dataclass
class InstalledSkill:
    """Local installed skill record (persisted in installed.yaml)."""

    name: str
    version: str
    source: SkillSource
    source_url: str | None = None
    installed_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    status: SkillStatus = SkillStatus.INSTALLED
    pinned_version: str | None = None
    publisher: str | None = None

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
        }


def row_to_installed_skill(row: dict[str, Any]) -> InstalledSkill:
    src = SkillSource((row.get("source") or "local").strip())
    stat = SkillStatus((row.get("status") or "installed").strip())
    ia = row.get("installed_at")
    ua = row.get("updated_at")
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
    )


__all__ = [
    "ClawHubSkillInfo",
    "InstalledSkill",
    "SkillSource",
    "SkillStatus",
    "row_to_installed_skill",
]
