# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""One-shot response extras for web chat (sources, response_kind) from orchestration paths."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.schemas.web_ui import WebResponseSourceItem

_lock = threading.Lock()
_pending: dict[str, Any] = {}


@dataclass
class WebTurnExtra:
    response_kind: str | None = None
    sources: list[WebResponseSourceItem] = field(default_factory=list)
    # e.g. "Tool: Public web read + Web search" for marketing web analysis
    tool_line: str | None = None


def set_web_turn_extra(
    response_kind: str,
    sources: list[WebResponseSourceItem] | None = None,
    *,
    tool_line: str | None = None,
) -> None:
    with _lock:
        _pending["web_turn"] = WebTurnExtra(
            response_kind=response_kind,
            sources=list(sources or []),
            tool_line=tool_line,
        )


def take_web_turn_extra() -> WebTurnExtra:
    with _lock:
        ex = _pending.pop("web_turn", None)
    return ex or WebTurnExtra()
