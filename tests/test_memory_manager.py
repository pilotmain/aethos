# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Tests for conversation memory enrichment."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.memory_manager import (
    detect_contradiction_hint,
    enrich_conversation_snapshot_for_llm,
)


def test_detect_contradiction_correction_cue() -> None:
    hint = detect_contradiction_hint(
        "Actually that's wrong",
        [{"role": "assistant", "text": "Done."}],
    )
    assert hint is not None
    assert "correcting" in hint.lower()


def test_enrich_snapshot_expands_recent(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = SimpleNamespace(
        recent_messages_json='[{"role":"user","text":"hi"},{"role":"assistant","text":"hello"}]'
    )

    def fake_settings() -> SimpleNamespace:
        return SimpleNamespace(
            nexa_conversation_memory_enabled=True,
            nexa_conversation_memory_turns=10,
        )

    monkeypatch.setattr("app.services.memory_manager.get_settings", fake_settings)
    snap_in: dict = {"recent_messages": [], "summary": None}
    out = enrich_conversation_snapshot_for_llm(snap_in, ctx, "ok thanks")  # type: ignore[arg-type]
    assert len(out["recent_messages"]) == 2
