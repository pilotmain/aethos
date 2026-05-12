# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Pluggable secret storage backends (Phase 54 MVP)."""

from __future__ import annotations

import logging
from typing import Protocol

from app.services.credentials.types import SecretRef

_log = logging.getLogger(__name__)


class CredentialBackend(Protocol):
    def store(self, name: str, value: str, scope: str) -> SecretRef: ...

    def read(self, ref: SecretRef, purpose: str) -> str: ...


class LocalEncryptedPlaceholder:
    """
    MVP: holds secrets in process memory only (lost on restart).

    Never logs secret values. Replace with OS keychain / KMS in production paths.
    """

    def __init__(self) -> None:
        self._mem: dict[tuple[str, str, str], str] = {}

    def store(self, name: str, value: str, scope: str) -> SecretRef:
        key_id = f"mem:{scope}:{name}"
        self._mem[(scope, name, key_id)] = value
        _log.info("credential_stored scope=%s name=%s", scope, name)
        return SecretRef(name=name, scope=scope, key_id=key_id)

    def read(self, ref: SecretRef, purpose: str) -> str:
        _ = purpose
        v = self._mem.get((ref.scope, ref.name, ref.key_id))
        if v is None:
            raise KeyError("secret not found")
        _log.info("credential_read scope=%s name=%s purpose=%s", ref.scope, ref.name, purpose[:80])
        return v


__all__ = ["CredentialBackend", "LocalEncryptedPlaceholder"]
