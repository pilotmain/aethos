"""Shorthand ``make a file X says Y`` must parse for host executor."""

from __future__ import annotations

from app.services.host_executor_intent import infer_host_executor_action, parse_file_write_intent


def test_make_file_says_parses() -> None:
    text = "make a file test.txt says Hello World"
    p = parse_file_write_intent(text)
    assert p is not None
    assert "test.txt" in str(p.get("filename"))
    assert "Hello World" in str(p.get("content"))


def test_infer_host_file_write() -> None:
    inf = infer_host_executor_action("make a file notes.txt says Hi")
    assert inf is not None
    assert inf.get("host_action") == "file_write"
