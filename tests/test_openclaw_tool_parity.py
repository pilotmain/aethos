# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Host / tool execution parity gates — see docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md §5."""

from __future__ import annotations

from app.services.host_executor import is_command_safe


def test_allowlisted_echo_is_command_safe() -> None:
    assert is_command_safe("echo parity_probe")
