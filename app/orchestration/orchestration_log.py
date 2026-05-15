"""Structured JSON lines under ``~/.aethos/logs/*.log`` (OpenClaw-style events)."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from app.core.paths import get_aethos_home_dir

_LOG = logging.getLogger(__name__)


def _logs_dir() -> Path:
    d = get_aethos_home_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def append_json_log(stem: str, event: str, **fields: Any) -> None:
    """Append one JSON object per line to ``~/.aethos/logs/{stem}.log``."""
    row: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "event": event,
        **fields,
    }
    line = json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n"
    try:
        path = _logs_dir() / f"{stem}.log"
        path.open("a", encoding="utf-8").write(line)
    except OSError as exc:
        _LOG.debug("json_log.write_failed stem=%s err=%s", stem, exc)


def log_orchestration_event(event: str, **fields: Any) -> None:
    append_json_log("orchestration", event, **fields)
    append_json_log("runtime", event, **fields)


def log_recovery_event(event: str, **fields: Any) -> None:
    append_json_log("recovery", event, **fields)


def log_agents_event(event: str, **fields: Any) -> None:
    append_json_log("agents", event, **fields)


def log_deployments_event(event: str, **fields: Any) -> None:
    append_json_log("deployments", event, **fields)


def log_gateway_event(event: str, **fields: Any) -> None:
    append_json_log("gateway", event, **fields)
