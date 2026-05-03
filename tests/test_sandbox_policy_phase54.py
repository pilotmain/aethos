from __future__ import annotations

from app.services.sandbox.types import SandboxMode
from app.services.sandbox.policy import resolve_effective_mode, resolve_sandbox_policy


def test_gvisor_not_auto_enabled() -> None:
    m, enforced, reason = resolve_effective_mode(SandboxMode.gvisor)
    assert m == SandboxMode.process
    assert enforced is False
    assert reason and "gvisor" in reason.lower()


def test_resolve_sandbox_policy_basic() -> None:
    p = resolve_sandbox_policy("demo_tool", frozenset({"read"}))
    assert p.enforced
    assert p.allowed_permissions == frozenset({"read"})
