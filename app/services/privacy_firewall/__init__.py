"""
Privacy firewall — redact / block / confirm before payloads reach external providers.

Worker missions use :func:`prepare_external_payload`; LLM strings use :func:`prepare_external_text`.
"""

from app.services.privacy_firewall.gateway import PrivacyBlockedError, prepare_external_payload, prepare_external_text

__all__ = ["PrivacyBlockedError", "prepare_external_payload", "prepare_external_text"]
