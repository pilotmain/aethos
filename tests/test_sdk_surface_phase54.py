from __future__ import annotations

from app.services.sdk.types import ProviderRefDict, SkillRefDict, TaskEventDict


def test_sdk_types_importable() -> None:
    e: TaskEventDict = {"task_id": "1", "type": "x", "payload": {}, "ts": "now"}
    assert e["task_id"] == "1"
    s: SkillRefDict = {"id": "a", "version": "1", "permissions": []}
    assert s["id"] == "a"
    p: ProviderRefDict = {"provider": "anthropic", "model": "x"}
    assert p["provider"] == "anthropic"
