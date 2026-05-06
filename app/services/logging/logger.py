"""Central ``nexa`` logger — use for mission, provider, and privacy audit lines."""

from __future__ import annotations

import logging

_LOG = logging.getLogger("aethos")
_LOG.setLevel(logging.INFO)

_TEXT_FMT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the shared Nexa logger or a child (``nexa.worker``, ``nexa.gateway``, …)."""
    if not name:
        return _LOG
    return logging.getLogger(f"nexa.{name}")


def _upgrade_root_stream_handlers(*, use_json: bool) -> None:
    """Ensure StreamHandler formatters redact secrets (handles pre-existing basicConfig)."""
    from app.core.logging import RedactingFormatter

    root = logging.getLogger()
    if use_json:
        from app.services.logging.json_formatter import NexaJsonFormatter

        for h in root.handlers:
            if isinstance(h, logging.StreamHandler) and not isinstance(h.formatter, NexaJsonFormatter):
                h.setFormatter(NexaJsonFormatter())
        return

    for h in root.handlers:
        if not isinstance(h, logging.StreamHandler):
            continue
        if isinstance(h.formatter, RedactingFormatter):
            continue
        old = h.formatter
        datefmt = getattr(old, "datefmt", None) if old is not None else None
        h.setFormatter(RedactingFormatter(_TEXT_FMT, datefmt=datefmt))


def configure_logging(level: int = logging.INFO) -> None:
    """Idempotent basic config if no handlers (API/bot startup); always prefer redacting formatters."""
    from app.core.config import get_settings
    from app.core.logging import RedactingFormatter

    root = logging.getLogger()
    use_json = bool(getattr(get_settings(), "log_json_format", False))

    if not root.handlers:
        root.setLevel(level)
        if use_json:
            h = logging.StreamHandler()
            from app.services.logging.json_formatter import NexaJsonFormatter

            h.setFormatter(NexaJsonFormatter())
            h.setLevel(level)
            root.addHandler(h)
        else:
            h = logging.StreamHandler()
            h.setFormatter(RedactingFormatter(_TEXT_FMT))
            h.setLevel(level)
            root.addHandler(h)
    else:
        _upgrade_root_stream_handlers(use_json=use_json)
        root.setLevel(level)

    _LOG.setLevel(level)


__all__ = ["get_logger", "configure_logging"]
