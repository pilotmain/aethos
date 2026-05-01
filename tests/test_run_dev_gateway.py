"""Gateway ``run dev`` prefix — parse + ordering before loose mission parser."""

from __future__ import annotations

from app.services.dev_runtime.run_dev_gateway import parse_run_dev_goal
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway
from app.services.missions.parser import parse_mission


def test_parse_run_dev_goal() -> None:
    assert parse_run_dev_goal("run dev: fix tests") == "fix tests"
    assert parse_run_dev_goal("run dev fix tests") == "fix tests"
    assert parse_run_dev_goal("run dev") == ""
    assert parse_run_dev_goal("Run DEV: ship it") == "ship it"
    assert parse_run_dev_goal("run developer tools") is None
    assert parse_run_dev_goal("Researcher: write summary") is None


def test_loose_parse_would_interpret_run_dev_line() -> None:
    """Documents why :meth:`~app.services.gateway.runtime.NexaGateway.handle_message` runs dev first."""
    m = parse_mission("run dev: fix failing tests")
    assert m is not None
    assert (m.get("agents") or m.get("tasks") or [])


def test_gateway_run_dev_no_workspace(nexa_runtime_clean) -> None:
    ctx = GatewayContext.from_channel("u_run_dev", "web", {})
    out = NexaGateway().handle_message(ctx, "run dev: fix tests", db=nexa_runtime_clean)
    assert out.get("mode") == "chat"
    assert "No dev workspaces" in (out.get("text") or "")
