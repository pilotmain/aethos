# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 15a — chunking, ActiveMemoryService, POST /memory/recall."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import get_settings
from app.services.memory.active_memory import ActiveMemoryService
from app.services.memory.chunking import chunk_text
from app.services.memory.memory_store import MemoryStore


def test_chunk_text_splits_long_input() -> None:
    text = "word " * 500
    chunks = chunk_text(text, max_chars=120, overlap=20)
    assert len(chunks) >= 2
    assert all(len(c) <= 130 for c in chunks)


def test_active_memory_recall_returns_hits(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path))
    monkeypatch.setenv("NEXA_ACTIVE_MEMORY_ENABLED", "true")
    monkeypatch.setenv("NEXA_ACTIVE_MEMORY_MIN_SCORE", "-1")
    monkeypatch.setenv("NEXA_ACTIVE_MEMORY_TOP_K", "12")
    get_settings.cache_clear()

    store = MemoryStore()
    store.append_entry(
        "user-phase15",
        kind="note",
        title="Infrastructure",
        body_md="Production PostgreSQL runs on RDS in us-east-1.",
    )
    svc = ActiveMemoryService(store)
    hits = svc.recall("user-phase15", "postgres database production region")
    assert len(hits) >= 1
    assert any("postgres" in str(h.get("text", "")).lower() or "rds" in str(h.get("text", "")).lower() for h in hits)


def test_memory_recall_api_bearer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NEXA_CRON_API_TOKEN", "test-mem-tok")
    monkeypatch.setenv("NEXA_MEMORY_DIR", str(tmp_path))
    monkeypatch.setenv("NEXA_ACTIVE_MEMORY_ENABLED", "true")
    monkeypatch.setenv("NEXA_ACTIVE_MEMORY_MIN_SCORE", "-1")
    get_settings.cache_clear()

    from fastapi.testclient import TestClient

    from app.main import app
    from app.services.memory.memory_store import MemoryStore

    MemoryStore().append_entry(
        "u-api",
        kind="note",
        title="T",
        body_md="hello world unique token xyz123",
    )

    c = TestClient(app)
    r = c.get("/api/v1/memory")
    assert r.status_code == 410

    r2 = c.post(
        "/api/v1/memory/recall",
        json={"query": "xyz123", "user_id": "u-api", "k": 5},
        headers={"Authorization": "Bearer test-mem-tok"},
    )
    assert r2.status_code == 200
    data = r2.json()
    assert data.get("ok") is True
    assert data.get("count", 0) >= 1
