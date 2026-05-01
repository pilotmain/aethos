"""Phase 25 — parse_test_failures."""

from __future__ import annotations

from app.services.dev_runtime.tester import parse_test_failures


def test_parser_extracts_pytest_failure_line() -> None:
    out = parse_test_failures(
        "FAILED tests/test_foo.py::test_bar - AssertionError: assert 1 == 2\n"
        "E   assert 1 == 2\n"
    )
    assert "FAILED" in out["summary"] or "AssertionError" in out["summary"]
    assert out["failure_count"] >= 1


def test_parser_collects_file_hints() -> None:
    out = parse_test_failures("tests/unit/test_x.py:42: AssertionError\n")
    assert any("test_x.py" in f for f in out["files"])
