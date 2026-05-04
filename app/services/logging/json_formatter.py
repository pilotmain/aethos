"""Optional JSON line formatter for stdout log aggregation (chain / approval fields on the record)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

# Keys we emit from ``Logger.info(..., extra={...})`` for host-executor / chain observability.
_NEXA_EXTRA_KEYS = frozenset(
    {
        "nexa_event",
        "job_id",
        "chain_step",
        "chain_total_steps",
        "host_action",
        "duration_ms",
        "success",
        "error",
        "chain_exit_reason",
        "chain_success_count",
        "chain_total_duration_ms",
        "chain_stop_on_failure",
        "approval_time_ms",
        "chain_length",
        "telegram_chat_id",
        "inner_actions",
        "nl_chain_pattern",
        "nl_repo_hint",
        "nl_content_preview",
    }
)


class NexaJsonFormatter(logging.Formatter):
    """One JSON object per line; merges whitelisted extra fields from the LogRecord."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()
        payload: dict = {
            "timestamp": ts,
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for k in _NEXA_EXTRA_KEYS:
            if k in record.__dict__ and record.__dict__[k] is not None:
                payload[k] = record.__dict__[k]
        return json.dumps(payload, default=str)
