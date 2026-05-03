"""Local NexaForge catalog — JSON on disk, validation before install."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import REPO_ROOT

from app.services.skills.draft import validate_skill_manifest

_DEFAULT_CATALOG = REPO_ROOT / "data" / "nexa_marketplace" / "catalog.json"


def load_catalog(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or _DEFAULT_CATALOG
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    if isinstance(raw, dict) and isinstance(raw.get("skills"), list):
        return [x for x in raw["skills"] if isinstance(x, dict)]
    return []


def catalog_entry_trust(meta: dict[str, Any]) -> float:
    try:
        return float(meta.get("trust_score") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def can_install_entry(meta: dict[str, Any]) -> tuple[bool, list[str]]:
    ok, errs = validate_skill_manifest(meta)
    sig = meta.get("signature")
    if sig is not None and not isinstance(sig, str):
        errs.append("invalid signature field")
    if catalog_entry_trust(meta) < 0.0:
        errs.append("invalid trust_score")
    return ok and not errs, errs


__all__ = ["can_install_entry", "catalog_entry_trust", "load_catalog"]
