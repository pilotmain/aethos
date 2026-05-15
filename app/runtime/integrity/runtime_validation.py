"""Compatibility shim — re-export :func:`validate_runtime_state`."""

from __future__ import annotations

from app.runtime.integrity.runtime_integrity import validate_runtime_state

__all__ = ["validate_runtime_state"]
