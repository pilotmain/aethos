"""Plugin registry — tools load once at startup and extend ``TOOLS``."""

from app.services.plugins.registry import (
    NexaPlugin,
    PluginRegistry,
    load_plugins,
    register_plugin,
)

__all__ = ["NexaPlugin", "PluginRegistry", "load_plugins", "register_plugin"]
