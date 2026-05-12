# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 44D — memory ranked for task context, not raw dumps."""

from __future__ import annotations

from app.services.autonomy.intelligence import build_intelligent_context
from app.services.tasks.unified_task import NexaTask


def test_build_intelligent_context_respects_query(monkeypatch) -> None:
    called: dict[str, str] = {}

    class FakeMI:
        def semantic_search(self, user_id: str, query: str, *, limit: int = 10):
            called["q"] = query
            return [{"id": "1", "title": "t1", "preview": "p1"}]

    task = NexaTask(
        id="1",
        type="dev",
        input="flaky payment webhook",
        context={},
        priority=10,
        auto_generated=True,
        origin="autonomy",
    )
    ctx = build_intelligent_context(task, user_id="u1", max_chars=500, memory_fn=FakeMI())
    assert "payment" in called.get("q", "")
    assert "prompt_injection" in ctx
    assert "flaky" in ctx["prompt_injection"] or "t1" in ctx["prompt_injection"]
