"""Phase 52A — memory bundle includes user notes on follow-up turns."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.memory.context_injection import build_memory_context_for_turn
from app.services.memory.memory_index import MemoryIndex
from app.services.memory.memory_store import MemoryStore


@pytest.fixture
def isolated_memory_store(tmp_path: Path) -> Path:
    return tmp_path


def test_followup_includes_stored_stack_terms(isolated_memory_store: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    uid = "phase52_mem_u1"
    mem_root = isolated_memory_store / "mem"
    store = MemoryStore(base_dir=mem_root)
    store.append_entry(
        uid,
        kind="note",
        title="Project stack",
        body_md="Uses EKS, MongoDB Atlas, Spring Boot, OIDC.",
    )

    fixed_index = MemoryIndex(store)
    monkeypatch.setattr(
        "app.services.memory.context_injection.MemoryIndex",
        lambda *a, **k: fixed_index,
    )

    q = "Given my project setup, what is the most likely reason Mongo auth fails?"
    ctx = build_memory_context_for_turn(uid, q)
    assert ctx.get("used") is True
    blob = (ctx.get("memory_context") or "").lower()
    assert "eks" in blob or "mongo" in blob
    assert "spring" in blob or "oidc" in blob
