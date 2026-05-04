"""Central ``nexa`` logger — use for mission, provider, and privacy audit lines."""

from __future__ import annotations

import logging

_LOG = logging.getLogger("nexa")
_LOG.setLevel(logging.INFO)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return the shared Nexa logger or a child (``nexa.worker``, ``nexa.gateway``, …)."""
    if not name:
        return _LOG
    return logging.getLogger(f"nexa.{name}")


def configure_logging(level: int = logging.INFO) -> None:
    """Idempotent basic config if no handlers (API/bot startup)."""
    from app.core.config import get_settings

    root = logging.getLogger()
    if root.handlers:
        _LOG.setLevel(level)
        return
    use_json = bool(getattr(get_settings(), "log_json_format", False))
    if use_json:
        h = logging.StreamHandler()
        from app.services.logging.json_formatter import NexaJsonFormatter

        h.setFormatter(NexaJsonFormatter())
        h.setLevel(level)
        root.setLevel(level)
        root.addHandler(h)
    else:
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        )
    _LOG.setLevel(level)


__all__ = ["get_logger", "configure_logging"]
