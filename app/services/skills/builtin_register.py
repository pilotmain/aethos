# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Register committed built-in plugin skills (YAML under ``builtin_plugins``)."""

from __future__ import annotations

import logging
from pathlib import Path

from app.services.skills.loader import load_skill_manifest
from app.services.skills.plugin_registry import get_plugin_skill_registry

logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent / "builtin_plugins"


def register_builtin_plugin_skills() -> None:
    """Load every ``builtin_plugins/*/skill.yaml`` once at API startup."""
    reg = get_plugin_skill_registry()
    if not _ROOT.is_dir():
        return
    for child in sorted(_ROOT.iterdir()):
        if not child.is_dir():
            continue
        manifest = child / "skill.yaml"
        if not manifest.is_file():
            continue
        try:
            skill = load_skill_manifest(manifest)
            reg.register(skill)
        except Exception as exc:  # noqa: BLE001
            logger.warning("builtin skill register failed %s: %s", manifest, exc)


__all__ = ["register_builtin_plugin_skills"]
