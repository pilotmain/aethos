"""Phase 33 — dev-runtime gateway shortcut is only invoked from NexaGateway."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_handle_run_dev_gateway_only_from_gateway_runtime() -> None:
    """Public callers must use :meth:`~app.services.gateway.runtime.NexaGateway.handle_message`."""
    offenders: list[str] = []
    gw_runtime = ROOT / "app" / "services" / "gateway" / "runtime.py"
    for path in (ROOT / "app").rglob("*.py"):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "handle_run_dev_gateway(" not in text:
            continue
        if path.resolve() == gw_runtime.resolve():
            continue
        if path.name == "run_dev_gateway.py":
            continue
        offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, "handle_run_dev_gateway called outside gateway/runtime: " + ", ".join(offenders)
