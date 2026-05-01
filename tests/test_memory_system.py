"""Phase 22 — persistent memory layer (filesystem store)."""

from __future__ import annotations

import uuid

from app.core.config import get_settings
from app.services.memory.memory_index import MemoryIndex
from app.services.memory.memory_store import MemoryStore


def test_memory_store_append_and_read(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path / "m"))
    get_settings.cache_clear()
    uid = f"web_mc_{uuid.uuid4().hex[:8]}"
    store = MemoryStore()
    store.append_entry(uid, kind="note", title="Hello", body_md="Body **text**", meta={"k": 1})
    doc = store.read_document(uid)
    assert doc["entry_count"] >= 1
    assert "Hello" in doc["full_markdown"]


def test_memory_index_recent_for_prompt(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path / "m"))
    get_settings.cache_clear()
    uid = f"web_ix_{uuid.uuid4().hex[:8]}"
    store = MemoryStore()
    store.append_entry(uid, kind="fact", title="Fact", body_md="Learned something", meta={})
    idx = MemoryIndex(store)
    blob = idx.recent_for_prompt(uid, max_chars=500)
    assert "Learned" in blob or "fact" in blob.lower()
