"""Unified credential vault facade."""

from __future__ import annotations

import logging
from threading import Lock

from app.core.config import get_settings

from app.services.credentials.providers import LocalEncryptedPlaceholder
from app.services.credentials.types import SecretRef

_log = logging.getLogger(__name__)

_LOCK = Lock()
_PLACEHOLDER = LocalEncryptedPlaceholder()
_ACCESS_AUDIT: list[dict[str, str]] = []


def _backend():
    s = get_settings()
    prov = (getattr(s, "nexa_credential_vault_provider", None) or "local").strip().lower()
    if prov != "local":
        _log.warning("vault provider %s not implemented; using local placeholder", prov)
    return _PLACEHOLDER


def store_secret(name: str, value: str, scope: str) -> SecretRef:
    with _LOCK:
        return _backend().store(name, value, scope)


def read_secret(ref: SecretRef, purpose: str) -> str:
    with _LOCK:
        out = _backend().read(ref, purpose)
        audit_secret_access(ref, purpose)
        return out


def audit_secret_access(ref: SecretRef, purpose: str) -> None:
    """Append-only access log — no secret material."""
    _ACCESS_AUDIT.append(
        {
            "scope": ref.scope[:64],
            "name": ref.name[:128],
            "purpose": purpose[:200],
        }
    )
    while len(_ACCESS_AUDIT) > 2000:
        del _ACCESS_AUDIT[:100]


def recent_audit_tail(limit: int = 20) -> list[dict[str, str]]:
    return list(_ACCESS_AUDIT[-limit:])


__all__ = ["audit_secret_access", "read_secret", "recent_audit_tail", "store_secret"]
