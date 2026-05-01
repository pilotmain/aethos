"""Policy modes for outbound content: block | redact | ask | allow_local_only | allow."""

# DO NOT MODIFY WITHOUT SECURITY REVIEW — policy semantics drive firewall outcomes.

from __future__ import annotations

from enum import Enum


class PrivacyPolicyMode(str, Enum):
    BLOCK = "block"
    REDACT = "redact"
    ASK = "ask"
    ALLOW_LOCAL_ONLY = "allow_local_only"
    ALLOW = "allow"


def default_external_mode() -> PrivacyPolicyMode:
    """Default for third-party API calls."""
    return PrivacyPolicyMode.REDACT
