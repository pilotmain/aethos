# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Channel routing parity — see docs/OPENCLAW_FUNCTIONAL_PARITY_DIRECTIVE.md §10."""

from __future__ import annotations

from app.services.channels.router import route_inbound


def test_route_inbound_web_returns_dict() -> None:
    out = route_inbound("hello", "parity_ch_u1", db=None, channel="web")
    assert isinstance(out, dict)
