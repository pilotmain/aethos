# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Dynamic cloud provider configuration loader (Phase 52d).

Merges YAML sources so later files override earlier providers with the same ``name``.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from app.services.cloud.registry import CloudProvider, CloudProviderRegistry, ProviderCapability

logger = logging.getLogger(__name__)

_PACKAGE_DEFAULT_REL = Path("config") / "cloud_providers_default.yaml"


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent.parent


def packaged_default_yaml_path() -> Path:
    return _repo_root() / _PACKAGE_DEFAULT_REL


def get_builtin_provider_names() -> frozenset[str]:
    """Names declared in the packaged default YAML (used to block removal of shipped providers)."""
    path = packaged_default_yaml_path()
    if not path.is_file():
        return frozenset()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as exc:
        logger.warning("Could not read builtin provider names from %s: %s", path, exc)
        return frozenset()
    out: list[str] = []
    for row in data.get("providers") or []:
        if not isinstance(row, dict):
            continue
        n = (row.get("name") or "").strip()
        if n:
            out.append(n.lower())
    return frozenset(out)


def _removable_drop_in_path(source_path: Path, provider_name: str) -> str | None:
    """If this file is ~/.aethos/cloud_providers.d/<name>.yaml, return its path for /remove_provider."""
    try:
        name = (provider_name or "").strip().lower()
        if not name:
            return None
        drop = (Path.home() / ".aethos" / "cloud_providers.d").resolve()
        src = source_path.resolve()
        if src.parent != drop:
            return None
        if src.stem.lower() != name:
            return None
        if src.suffix.lower() not in (".yaml", ".yml"):
            return None
        return str(src)
    except Exception:
        return None


def _parse_capabilities(raw: Any, *, provider_name: str) -> list[ProviderCapability]:
    out: list[ProviderCapability] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        s = str(item).strip()
        if not s:
            continue
        try:
            out.append(ProviderCapability(s))
        except ValueError:
            logger.warning("Unknown capability %r for provider %s — skipping", s, provider_name)
    return out


def _str_list(val: Any) -> list[str]:
    if not isinstance(val, list):
        return []
    return [str(x) for x in val]


def _commands_map(cmds: Any) -> dict[str, list[str]]:
    if not isinstance(cmds, dict):
        return {}
    out: dict[str, list[str]] = {}
    for k, v in cmds.items():
        key = str(k).strip().lower()
        if key and isinstance(v, list):
            out[key] = _str_list(v)
    return out


def _row_to_provider(data: dict[str, Any]) -> CloudProvider | None:
    name = (data.get("name") or "").strip().lower()
    display_name = (data.get("display_name") or "").strip()
    cli_package = (data.get("cli_package") or data.get("cli") or "").strip() or None
    if not name or not display_name:
        logger.warning("Skipping provider row missing name or display_name")
        return None

    cmds = _commands_map(data.get("commands"))
    caps = _parse_capabilities(data.get("capabilities"), provider_name=name)

    return CloudProvider(
        name=name,
        display_name=display_name,
        cli_package=cli_package,
        install_command=(data.get("install_command") or None),
        token_env_var=(data.get("token_env_var") or None),
        project_id_env_var=(data.get("project_id_env_var") or None),
        capabilities=caps,
        detect_patterns=_str_list(data.get("detect_patterns")),
        deploy_command=list(cmds.get("deploy") or []),
        logs_command=list(cmds.get("logs") or []),
        status_command=list(cmds.get("status") or []),
        destroy_command=list(cmds.get("destroy") or []),
        list_command=list(cmds.get("list") or []),
        env_command=list(cmds.get("env") or []),
        plan_command=list(cmds.get("plan") or []),
        removable_config_file=None,
    )


def _ordered_config_paths() -> list[Path]:
    paths: list[Path] = [packaged_default_yaml_path()]
    paths.append(Path("/etc/aethos/cloud_providers.yaml"))
    drop_dir = Path.home() / ".aethos" / "cloud_providers.d"
    if drop_dir.is_dir():
        drop_ins = sorted(drop_dir.glob("*.yaml")) + sorted(drop_dir.glob("*.yml"))
        paths.extend(drop_ins)
    paths.append(Path.home() / ".aethos" / "cloud_providers.yaml")
    return paths


def load_registry_from_config() -> CloudProviderRegistry:
    """Load and merge all provider YAML sources into a new registry."""
    registry = CloudProviderRegistry()
    merged: dict[str, tuple[CloudProvider, Path]] = {}

    for path in _ordered_config_paths():
        if not path.is_file():
            if path == packaged_default_yaml_path():
                logger.error("Packaged cloud provider defaults missing: %s", path)
            continue
        try:
            with path.open("r", encoding="utf-8") as f:
                doc = yaml.safe_load(f)
        except Exception as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            continue
        if not doc or not isinstance(doc, dict):
            continue
        providers = doc.get("providers")
        if not isinstance(providers, list):
            continue
        for row in providers:
            if not isinstance(row, dict):
                continue
            prov = _row_to_provider(row)
            if prov is None:
                continue
            merged[prov.name] = (prov, path)
            logger.debug("Cloud provider %r from %s", prov.name, path)

    for name, (prov, src) in merged.items():
        removable = _removable_drop_in_path(src, name)
        prov.removable_config_file = removable
        registry.register(prov)

    logger.info("Loaded %s cloud provider(s) from config", len(merged))
    return registry


def reload_providers() -> CloudProviderRegistry:
    """Reload providers from disk (used by get_provider_registry(force_reload=True))."""
    return load_registry_from_config()
