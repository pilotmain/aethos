"""Phase 25 — platform detection smoke tests."""

from __future__ import annotations

from aethos_cli.platform import detect, human_os_line


def test_detect_returns_core_keys() -> None:
    info = detect()
    assert "os" in info and "arch" in info
    assert "python_version" in info
    line = human_os_line(info)
    assert isinstance(line, str) and len(line) >= 3

