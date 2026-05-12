# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 22 — all channels funnel through gateway."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.gateway.context import GatewayContext
from app.services.channels.router import route_inbound


def test_route_inbound_calls_gateway_handle_message() -> None:
    with patch("app.services.channels.router.NexaGateway") as gw_cls:
        inst = MagicMock()
        inst.handle_message.return_value = {"mode": "chat", "text": "x"}
        gw_cls.return_value = inst
        db = MagicMock()
        out = route_inbound("hello", "web_u1", db=db, channel="telegram")
        assert out == {"mode": "chat", "text": "x"}
        inst.handle_message.assert_called_once()
        kw = inst.handle_message.call_args
        assert isinstance(kw[0][0], GatewayContext)
        assert kw[0][0].user_id == "web_u1"
        assert kw[0][0].channel == "telegram"
        assert kw[0][1] == "hello"
        assert kw[1]["db"] is db
