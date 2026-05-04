# DO NOT MODIFY WITHOUT SECURITY REVIEW — vendor SDK construction guard.

"""
Vendor LLM SDK access — **only** via :func:`build_openai_client` / :func:`build_anthropic_client`.

Instantiation is guarded so arbitrary modules cannot construct SDK clients; allowed call sites
are the provider implementations plus vetted orchestration modules (see ``_ALLOW_VENDOR_SDK_MODULES``).
"""

from __future__ import annotations

import inspect
import logging
from typing import Any

_log = logging.getLogger(__name__)

CRITICAL_BOUNDARY_MSG = (
    "CRITICAL: ARCHITECTURE VIOLATION — vendor LLM SDK clients must only be constructed "
    "via app.services.providers.sdk builders inside approved modules (providers bundle, "
    "llm_service, response_composer). Use app.services.providers.gateway.call_provider from elsewhere."
)

_ORCHESTRATION_MODULES = (
    "app.services.llm_service",
    "app.services.response_composer",
    "app.services.llm",
)


def _allowed_runtime_module(name: str) -> bool:
    if name.startswith("app.services.providers."):
        return True
    for base in _ORCHESTRATION_MODULES:
        if name == base or name.startswith(base + "."):
            return True
    return False


def _vendor_sdk_callsite_allowed() -> bool:
    for fr in inspect.stack()[2:]:
        mod = inspect.getmodule(fr.frame)
        name = getattr(mod, "__name__", "") if mod else ""
        if not name:
            continue
        if name.startswith(
            (
                "tests.",
                "pytest",
                "unittest.",
                "_pytest.",
            ),
        ):
            return True
        if _allowed_runtime_module(name):
            return True
    _log.error(CRITICAL_BOUNDARY_MSG)
    return False


def build_openai_client(**kwargs: Any) -> Any:
    """Construct an OpenAI SDK client (guarded)."""
    if not _vendor_sdk_callsite_allowed():
        raise RuntimeError(CRITICAL_BOUNDARY_MSG)
    from openai import OpenAI as _OpenAI

    return _OpenAI(**kwargs)


def build_anthropic_client(**kwargs: Any) -> Any:
    """Construct an Anthropic SDK client (guarded)."""
    if not _vendor_sdk_callsite_allowed():
        raise RuntimeError(CRITICAL_BOUNDARY_MSG)
    import anthropic as _anthropic

    return _anthropic.Anthropic(**kwargs)


__all__ = ["build_openai_client", "build_anthropic_client", "CRITICAL_BOUNDARY_MSG"]
