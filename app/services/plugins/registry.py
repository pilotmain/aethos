"""
Nexa plugin host — register tool descriptors that merge into the global tool map.

All external tool execution still routes through the provider gateway (privacy firewall).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.services.tools.registry import ToolDescriptor, register_tool

PLUGINS: list[Any] = []


@runtime_checkable
class NexaPlugin(Protocol):
    name: str

    def register(self, registry: "PluginRegistry") -> None: ...


class PluginRegistry:
    """Plugins add tool metadata; workers still resolve providers via :mod:`app.services.tools.registry`."""

    def add_tool(self, spec: dict[str, Any]) -> None:
        name = str(spec.get("name") or "").strip()
        if not name:
            raise ValueError("tool name is required")
        td = ToolDescriptor(
            name=name,
            description=str(spec.get("description") or name),
            risk_level=str(spec.get("risk_level") or "model"),
            provider=str(spec.get("provider") or "local_stub"),
            pii_policy=str(spec.get("pii_policy") or "firewall_required"),
            enabled=bool(spec.get("enabled", True)),
        )
        register_tool(td)


def register_plugin(plugin: NexaPlugin | Any) -> None:
    """Append a plugin instance (called from plugin modules at import time)."""
    PLUGINS.append(plugin)


def load_plugins() -> list[Any]:
    """
    Load built-in and registered plugins once.

    Side effect: each plugin's ``register`` runs against a fresh :class:`PluginRegistry`.
    """
    if getattr(load_plugins, "_done", False):
        return PLUGINS

    reg = PluginRegistry()
    # Built-ins ship in ``app.plugins``; importing registers via ``register_plugin``.
    try:
        import app.plugins.builtin  # noqa: F401
    except Exception:
        pass

    for p in list(PLUGINS):
        try:
            p.register(reg)
        except Exception:
            continue

    load_plugins._done = True  # type: ignore[attr-defined]
    return PLUGINS


def plugin_manifest() -> list[dict[str, Any]]:
    """Lightweight introspection for Mission Control / debugging."""
    out: list[dict[str, Any]] = []
    for p in PLUGINS:
        name = getattr(p, "name", type(p).__name__)
        out.append({"name": name})
    return out


__all__ = [
    "NexaPlugin",
    "PluginRegistry",
    "PLUGINS",
    "register_plugin",
    "load_plugins",
    "plugin_manifest",
]
