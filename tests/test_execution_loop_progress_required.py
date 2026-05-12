# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""P0 — handled execution-loop replies include Progress / arrow steps."""

from __future__ import annotations

import uuid

import pytest

from app.services.execution_loop import ExecutionLoopResult
from app.services.gateway.context import GatewayContext
from app.services.gateway.runtime import NexaGateway


@pytest.mark.usefixtures("nexa_runtime_clean")
def test_handled_loop_response_includes_progress_markers(monkeypatch, db_session) -> None:
    monkeypatch.setattr(
        "app.services.execution_loop.try_execute_or_explain",
        lambda **kw: ExecutionLoopResult(
            handled=True,
            text="### Progress\n\n→ Starting investigation\n→ Checking Railway access\n\ndetails…",
        ),
    )

    uid = f"el_{uuid.uuid4().hex[:10]}"
    gctx = GatewayContext(user_id=uid, channel="web")
    out = NexaGateway().handle_message(gctx, "retry railway logs check", db=db_session)
    t = out.get("text") or ""
    assert ("→" in t) or ("progress" in t.lower())
