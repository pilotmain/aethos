# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Explicit CLI backend registry (OpenClaw-style): resolve ``vercel``, ``gh``, etc. to concrete binaries.

Resolution order per backend: configured absolute path (``os.environ`` then :class:`~app.core.config.Settings`)
→ enriched PATH via :func:`~app.services.operator_cli_path.which_operator_cli` → bare name for subprocess/shell.

Unknown CLI names return ``[name, *args]`` unchanged (backward compatible).
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from app.services.operator_cli_path import which_operator_cli

logger = logging.getLogger("nexa.cli_backends")

_SHORT_TO_ATTR: dict[str, str] = {
    "vercel": "nexa_operator_cli_vercel_abs",
    "gh": "nexa_operator_cli_gh_abs",
    "git": "nexa_operator_cli_git_abs",
    "railway": "nexa_operator_cli_railway_abs",
}

_CLI_ENV_KEYS: dict[str, str] = {
    "vercel": "NEXA_OPERATOR_CLI_VERCEL_ABS",
    "gh": "NEXA_OPERATOR_CLI_GH_ABS",
    "git": "NEXA_OPERATOR_CLI_GIT_ABS",
    "railway": "NEXA_OPERATOR_CLI_RAILWAY_ABS",
}

_EXTRA_ENV_BACKENDS: tuple[tuple[str, str], ...] = (
    ("codex", "CODEX_CLI_PATH"),
    ("claude", "CLAUDE_CLI_PATH"),
)


def _abs_debug_enabled() -> bool:
    return (os.environ.get("NEXA_OPERATOR_CLI_ABS_DEBUG") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def operator_abs_debug_enabled() -> bool:
    """True when ``NEXA_OPERATOR_CLI_ABS_DEBUG`` requests verbose CLI / shell embedding logs."""
    return _abs_debug_enabled()


def configured_absolute_raw(short: str) -> str:
    """Non-empty absolute-path string from env (preferred) or Pydantic Settings."""
    env_key = _CLI_ENV_KEYS.get(short)
    if env_key:
        v = (os.environ.get(env_key) or "").strip()
        if v:
            return v
    attr = _SHORT_TO_ATTR.get(short)
    if not attr:
        return ""
    try:
        from app.core.config import get_settings

        return (getattr(get_settings(), attr, None) or "").strip()
    except Exception:  # noqa: BLE001
        return ""


@dataclass
class CLIBackend:
    """One logical CLI (``vercel``, ``gh``, …) and how to resolve its executable."""

    name: str
    command: str
    args: List[str] = field(default_factory=list)
    env_vars: Dict[str, str] = field(default_factory=dict)
    persistent_session: bool = False

    def resolve_command(self) -> Optional[str]:
        """Return a concrete executable path, or ``None`` to keep the bare ``name``."""
        p = Path(self.command).expanduser()
        if os.path.isabs(self.command):
            try:
                if p.is_file() and os.access(p, os.X_OK):
                    return str(p.resolve())
            except OSError:
                pass
            logger.warning(
                "nexa.cli_backends: configured absolute path for %s not usable: %s",
                self.name,
                self.command,
            )
        else:
            w = which_operator_cli(self.command) or shutil.which(self.command)
            if w:
                return w

        # Fall back to canonical tool name on PATH
        w = which_operator_cli(self.name) or shutil.which(self.name)
        return w


class CLIBackendRegistry:
    """Registered backends; built-in operator CLIs plus optional codex/claude env paths."""

    def __init__(self) -> None:
        self._backends: Dict[str, CLIBackend] = {}
        self._load_builtin_defaults()
        self._load_extra_env_clis()

    def _load_builtin_defaults(self) -> None:
        for name in ("vercel", "gh", "git", "railway"):
            cfg = configured_absolute_raw(name)
            cmd = cfg if cfg else name
            self.register(CLIBackend(name=name, command=cmd))

    def _load_extra_env_clis(self) -> None:
        for name, env_key in _EXTRA_ENV_BACKENDS:
            raw = (os.environ.get(env_key) or "").strip()
            if raw:
                self.register(CLIBackend(name=name, command=raw))

    def register(self, backend: CLIBackend) -> None:
        self._backends[backend.name] = backend

    def get(self, name: str) -> Optional[CLIBackend]:
        return self._backends.get(name)

    def resolve_cli_command(self, name: str, args: Optional[List[str]] = None) -> List[str]:
        tail = list(args or [])
        backend = self.get(name)
        if not backend:
            return [name] + tail

        raw_cfg = configured_absolute_raw(name)
        if raw_cfg:
            p = Path(raw_cfg).expanduser()
            try:
                exists = p.is_file()
                executable = bool(exists and os.access(p, os.X_OK))
                if _abs_debug_enabled():
                    logger.info(
                        "[operator_cli_absolute] %s: path=%s exists=%s executable=%s",
                        name,
                        raw_cfg,
                        exists,
                        executable,
                    )
                if executable:
                    resolved = str(p.resolve())
                    before = [name] + tail
                    after = [resolved] + tail
                    if _abs_debug_enabled():
                        logger.info(
                            "[operator_cli_absolute] Rewriting argv: %r -> %r",
                            before,
                            after,
                        )
                    return after
            except OSError as exc:
                if _abs_debug_enabled():
                    logger.info(
                        "[operator_cli_absolute] %s: path=%s error=%s",
                        name,
                        raw_cfg,
                        exc,
                    )

        resolved = backend.resolve_command()
        before = [name] + tail
        after = ([resolved] + tail) if resolved else before
        if _abs_debug_enabled() and before != after:
            logger.info(
                "[operator_cli_absolute] Rewriting argv: %r -> %r",
                before,
                after,
            )
        return after


_cli_registry_singleton: Optional[CLIBackendRegistry] = None


def _get_cli_registry() -> CLIBackendRegistry:
    global _cli_registry_singleton  # noqa: PLW0603
    if _cli_registry_singleton is None:
        _cli_registry_singleton = CLIBackendRegistry()
    return _cli_registry_singleton


def get_cli_backend(name: str) -> Optional[CLIBackend]:
    """Return the registered backend for ``name``, if any."""
    return _get_cli_registry().get(name)


def reset_cli_backend_registry() -> None:
    """Drop the lazy singleton so the next call reloads env/settings (tests only)."""
    global _cli_registry_singleton  # noqa: PLW0603
    _cli_registry_singleton = None


def get_cli_command(cli_name: str, args: Optional[List[str]] = None) -> List[str]:
    """
    Resolve ``cli_name`` and arguments to an argv list suitable for ``subprocess`` / shell allowlists.

    Unknown ``cli_name`` values pass through as ``[cli_name, *args]``.
    """
    return _get_cli_registry().resolve_cli_command(cli_name, args)


def register_cli_backend(
    name: str,
    command: str,
    *,
    persistent_session: bool = False,
    extra_env: Optional[Dict[str, str]] = None,
) -> None:
    """Register or replace a backend at runtime (tests / plugins)."""
    _get_cli_registry().register(
        CLIBackend(
            name=name,
            command=command,
            env_vars=dict(extra_env or {}),
            persistent_session=persistent_session,
        )
    )


__all__ = [
    "CLIBackend",
    "CLIBackendRegistry",
    "configured_absolute_raw",
    "get_cli_backend",
    "get_cli_command",
    "operator_abs_debug_enabled",
    "register_cli_backend",
    "reset_cli_backend_registry",
]
