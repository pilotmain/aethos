# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase B — nexa-ext-pro package + licensed hooks."""

from __future__ import annotations

import types

import pytest

pytest.importorskip("nexa_ext.sandbox")

import nexa_ext.dev_execution as nexa_dev_execution

from app.services.execution_trigger import should_auto_execute_dev
from app.services.llm_routing import map_pro_routing_model_key, resolve_anthropic_model_for_composer
from app.services.licensing.features import FEATURE_AUTO_DEV, FEATURE_MEMORY_INTEL, FEATURE_SMART_ROUTING
from app.services.memory.memory_index import MemoryIndex
from app.services.memory.pro_intel import apply_pro_memory_ranking


def test_nexa_ext_routing_choose_model() -> None:
    import nexa_ext.routing as r

    assert r.choose_model("dev", "low", 1.0) == "claude-strong"
    assert r.choose_model("chat", "low", 1.0) == "local-ollama"


def test_map_pro_routing_model_key() -> None:
    assert map_pro_routing_model_key("balanced").startswith("claude")


def test_resolve_model_without_license(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.llm_routing.has_pro_feature", lambda _x: False)
    fake_ctx = types.SimpleNamespace(
        intent="stuck_dev",
        behavior="unstick",
        user_message="long " * 40,
    )
    m = resolve_anthropic_model_for_composer(fake_ctx)
    assert m and isinstance(m, str)


def test_resolve_model_with_pro_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Licensed smart routing returns symbolic tier mapped to a concrete model id."""
    monkeypatch.setattr(
        "app.services.llm_routing.has_pro_feature",
        lambda f: f == FEATURE_SMART_ROUTING,
    )
    fake_ctx = types.SimpleNamespace(
        intent="stuck_dev",
        behavior="unstick",
        user_message="long " * 40,
    )
    m = resolve_anthropic_model_for_composer(fake_ctx)
    assert m and isinstance(m, str)


def test_memory_intel_rerank(monkeypatch: pytest.MonkeyPatch) -> None:
    entries = [
        {"title": "Mongo Atlas", "preview": "connection string", "_similarity": 0.8},
        {"title": "Redis cache", "preview": "ttl notes", "_similarity": 0.82},
    ]
    monkeypatch.setattr(
        "app.services.memory.pro_intel.get_extension",
        lambda name: __import__("nexa_ext.memory_intel", fromlist=["x"]) if name == "memory_intel" else None,
    )
    monkeypatch.setattr(
        "app.services.memory.pro_intel.has_pro_feature",
        lambda f: f == FEATURE_MEMORY_INTEL,
    )
    out = apply_pro_memory_ranking("u1", "mongo connection atlas", entries)
    assert len(out) == 2
    titles = [str(o.get("title") or "") for o in out]
    assert "Mongo Atlas" in titles[0]


def test_auto_dev_pro_extension(monkeypatch: pytest.MonkeyPatch) -> None:
    """OSS rejects medium-risk auto-dev; Pro extension may still allow clear error signals."""
    monkeypatch.setattr(
        "app.services.extensions.get_extension",
        lambda name: nexa_dev_execution if name == "dev_execution" else None,
    )
    monkeypatch.setattr(
        "app.services.licensing.features.has_pro_feature",
        lambda f: f == FEATURE_AUTO_DEV,
    )
    monkeypatch.setattr(
        "app.services.execution_trigger.assess_interaction_risk",
        lambda _t: "medium",
    )
    ok = should_auto_execute_dev(
        "compile failed with error TS2322 in middleware",
        "stuck_dev",
        workspace_count=1,
    )
    assert ok is True


def test_semantic_search_attaches_similarity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.memory.memory_store.MemoryStore.list_entries",
        lambda self, user_id, limit=500: [
            {"title": "alpha", "preview": "beta gamma delta"},
        ],
    )
    monkeypatch.setattr("app.services.memory.pro_intel.has_pro_feature", lambda _f: False)
    mi = MemoryIndex()
    hits = mi.semantic_search("u", "gamma beta", limit=5)
    assert hits
    assert "_similarity" in hits[0]
