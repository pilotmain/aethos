"""Sandbox mode declarations — unsupported modes must never report as active."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, FrozenSet


class SandboxMode(str, Enum):
    disabled = "disabled"
    process = "process"
    docker = "docker"
    gvisor = "gvisor"
    firecracker = "firecracker"


@dataclass(frozen=True, slots=True)
class SandboxPolicy:
    mode: SandboxMode
    enforced: bool
    unsupported_reason: str | None
    """Human-readable when ``enforced`` is False but a stricter mode was requested."""
    allowed_permissions: FrozenSet[str]


__all__ = ["SandboxMode", "SandboxPolicy"]
