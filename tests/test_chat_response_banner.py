# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Universal response formatter (opt-in beautiful mode)."""

from __future__ import annotations

from unittest.mock import patch

from app.services.chat_response_banner import (
    ResponseFormatter,
    ResponseType,
    apply_gateway_response_style,
    looks_chat_preformatted,
)


def test_format_basic() -> None:
    out = ResponseFormatter.format(
        "Done",
        ResponseType.SUCCESS,
        items=[{"label": "Path", "value": "/tmp/a.txt", "status": "success"}],
        tip="Next: open the file",
    )
    assert "✅" in out
    assert "**DONE**" in out
    assert "/tmp/a.txt" in out
    assert "Next:" in out


def test_beautiful_wrap_skips_markdown() -> None:
    assert looks_chat_preformatted("## Hello") is True
    body = apply_gateway_response_style("general_chat", "## Hello\n\nworld")
    assert body.startswith("##")


def test_beautiful_wrap_plain_when_enabled() -> None:
    class S:
        nexa_response_format = "beautiful"

    with patch("app.core.config.get_settings", return_value=S()):
        body = apply_gateway_response_style("goal_completed", "All steps ok.")
    assert "✅" in body
    assert "GOAL RUN" in body or "goal run".upper() in body.upper()
    assert "All steps ok." in body


def test_simple_mode_noop() -> None:
    class S:
        nexa_response_format = "simple"

    with patch("app.core.config.get_settings", return_value=S()):
        t = apply_gateway_response_style(None, "hello")
    assert t == "hello"
