# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""TTY-aware setup modes for one-curl interactive installer flows."""

from __future__ import annotations

import os
import sys

SETUP_MODES = ("interactive", "non_interactive", "ci", "repair", "resume", "review")

_tty_attached = False


def attach_setup_tty() -> bool:
    """Reattach stdin to /dev/tty so ``curl | bash`` can still prompt."""
    global _tty_attached
    if noninteractive_setup():
        return False
    if sys.stdin.isatty():
        return True
    if not os.path.exists("/dev/tty"):
        return False
    try:
        tty_fd = os.open("/dev/tty", os.O_RDWR)
        try:
            os.dup2(tty_fd, 0)
        finally:
            os.close(tty_fd)
        _tty_attached = True
        return sys.stdin.isatty()
    except OSError:
        return False


def resolve_setup_mode(*, install_kind: str | None = None) -> str:
    kind = (install_kind or os.environ.get("NEXA_SETUP_KIND") or "").strip().lower()
    if kind == "repair":
        return "repair"
    if (os.environ.get("NEXA_NONINTERACTIVE") or "").strip().lower() in ("1", "true", "yes"):
        return "non_interactive"
    if (os.environ.get("CI") or "").strip().lower() == "true":
        return "ci"
    if (os.environ.get("AETHOS_SETUP_CI") or "").strip().lower() in ("1", "true", "yes"):
        return "ci"
    if (os.environ.get("AETHOS_SETUP_REVIEW") or "").strip().lower() in ("1", "true", "yes"):
        return "review"
    if (os.environ.get("AETHOS_SETUP_RESUME") or "").strip().lower() in ("1", "true", "yes"):
        return "resume"
    if sys.stdin.isatty() or _tty_attached:
        return "interactive"
    return "non_interactive"


def setup_interactive() -> bool:
    return resolve_setup_mode() in ("interactive", "repair", "resume", "review")


def noninteractive_setup() -> bool:
    return resolve_setup_mode() in ("non_interactive", "ci")


def initialize_setup_interactive(*, install_kind: str | None = None) -> str:
    """Attach TTY when possible and return resolved setup mode."""
    attach_setup_tty()
    mode = resolve_setup_mode(install_kind=install_kind)
    os.environ.setdefault("AETHOS_SETUP_MODE", mode)
    if mode in ("non_interactive", "ci"):
        os.environ.setdefault("NEXA_NONINTERACTIVE", "1")
    return mode


__all__ = [
    "SETUP_MODES",
    "attach_setup_tty",
    "initialize_setup_interactive",
    "noninteractive_setup",
    "resolve_setup_mode",
    "setup_interactive",
]
