"""
Privacy firewall — redact / block / confirm before payloads reach external providers.

Worker missions use :func:`prepare_external_payload`; LLM strings use :func:`prepare_external_text`.
"""

# DO NOT MODIFY WITHOUT SECURITY REVIEW — package entrypoints affect all outbound privacy.

from app.services.privacy_firewall.gateway import (
    PrivacyBlockedError,
    normalize_pii_policy,
    prepare_external_payload,
    prepare_external_text,
)

__all__ = ["PrivacyBlockedError", "normalize_pii_policy", "prepare_external_payload", "prepare_external_text"]
