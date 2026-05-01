"""In-memory local file intelligence helpers (no indexing)."""

from __future__ import annotations

from unittest.mock import patch

from app.services.local_file_intel import (
    analyze_local_file_bundle,
    chunk_text,
    parse_file_bundle,
)


def test_parse_file_bundle() -> None:
    raw = """=== FILE: a/b.md ===
hello

=== FILE: c/d.txt ===
world
"""
    pairs = parse_file_bundle(raw)
    assert len(pairs) == 2
    assert pairs[0][0] == "a/b.md"
    assert "hello" in pairs[0][1]


def test_chunk_text() -> None:
    long = "x" * 8000
    chunks = chunk_text(long, max_chars=3500)
    assert len(chunks) >= 2
    assert sum(len(c) for c in chunks) == len(long)


def test_analyze_fallback_without_llm() -> None:
    bundle = "=== FILE: README.md ===\n# Hi\n"
    out = analyze_local_file_bundle(user_question="What is this?", operation="summarize", raw_bundle=bundle)
    assert "### Summary" in out


def test_analyze_mock_llm() -> None:
    bundle = "=== FILE: x.txt ===\none"
    with patch(
        "app.services.llm_service.call_primary_llm_text",
        return_value="### Summary\n\nok\n### Key findings\n\nx\n### Relevant files\n\nx\n### Recommendation\n\nx\n",
    ):
        out = analyze_local_file_bundle(user_question="?", operation="summarize", raw_bundle=bundle)
    assert "ok" in out.lower()
