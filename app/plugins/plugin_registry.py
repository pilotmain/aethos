# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Plugin registry — manifests + provider targets (Phase 2 Step 8)."""

from __future__ import annotations

from typing import Any

from app.plugins.plugin_manifest import PluginManifest

_MANIFESTS: dict[str, PluginManifest] = {}

_BUILTIN_PROVIDER_PLUGINS: tuple[PluginManifest, ...] = (
    PluginManifest(
        plugin_id="vercel-provider",
        name="Vercel",
        capabilities=["deployments", "logs", "redeploy", "restart"],
        permissions=["provider.vercel"],
    ),
    PluginManifest(
        plugin_id="railway-provider",
        name="Railway",
        capabilities=["deployments", "logs"],
        permissions=["provider.railway"],
    ),
    PluginManifest(
        plugin_id="fly-provider",
        name="Fly.io",
        capabilities=["deployments", "logs"],
        permissions=["provider.fly"],
    ),
    PluginManifest(
        plugin_id="netlify-provider",
        name="Netlify",
        capabilities=["deployments", "logs"],
        permissions=["provider.netlify"],
    ),
    PluginManifest(
        plugin_id="cloudflare-provider",
        name="Cloudflare",
        capabilities=["deployments", "logs"],
        permissions=["provider.cloudflare"],
    ),
    PluginManifest(
        plugin_id="github-provider",
        name="GitHub",
        capabilities=["repos", "actions"],
        permissions=["provider.github"],
    ),
    PluginManifest(plugin_id="discord-channel", name="Discord", capabilities=["channel"], permissions=["channel.discord"]),
    PluginManifest(plugin_id="slack-channel", name="Slack", capabilities=["channel"], permissions=["channel.slack"]),
    PluginManifest(
        plugin_id="telegram-channel",
        name="Telegram",
        capabilities=["channel"],
        permissions=["channel.telegram"],
    ),
    PluginManifest(
        plugin_id="aethos-builtin-tools",
        name="AethOS Builtin Tools",
        capabilities=["tools"],
        runtime_hooks=["tool_register"],
    ),
)


def _seed_builtin() -> None:
    if _MANIFESTS:
        return
    for m in _BUILTIN_PROVIDER_PLUGINS:
        _MANIFESTS[m.plugin_id] = m


def register_manifest(manifest: PluginManifest | dict[str, Any]) -> PluginManifest:
    m = manifest if isinstance(manifest, PluginManifest) else PluginManifest.from_dict(manifest)
    _MANIFESTS[m.plugin_id] = m
    return m


def list_plugin_manifests() -> list[dict[str, Any]]:
    _seed_builtin()
    return [m.to_dict() for m in _MANIFESTS.values()]


def get_plugin_manifest(plugin_id: str) -> dict[str, Any] | None:
    _seed_builtin()
    m = _MANIFESTS.get((plugin_id or "").strip())
    return m.to_dict() if m else None
