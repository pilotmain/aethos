from __future__ import annotations

from app.services.memory.provenance import enrich_memory_value


def test_enrich_memory_value_fields() -> None:
    v = enrich_memory_value({"note": "stack"}, source="chat", source_ref="m1", confidence=0.8)
    assert v["note"] == "stack"
    assert v["source"] == "chat"
    assert v["source_ref"] == "m1"
    assert v["version"] == 1
    assert 0.79 < float(v["confidence"]) <= 0.8
