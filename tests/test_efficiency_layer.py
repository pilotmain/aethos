"""Phase 45F — autonomy context compression."""

from __future__ import annotations

from app.services.autonomy.efficiency import compress_context


def test_compress_truncates_strings() -> None:
    long_s = "x" * 5000
    out = compress_context({"a": long_s, "b": [1, 2, 3, 4]}, max_string=100, max_list_items=2)
    assert len(out["a"]) <= 101
    assert len(out["b"]) == 2


def test_compress_nested_dict() -> None:
    out = compress_context({"outer": {"inner": "y" * 300}}, max_string=50)
    assert isinstance(out["outer"], dict)
    assert len(out["outer"]["inner"]) <= 51
