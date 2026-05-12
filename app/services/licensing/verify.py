# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Offline verification for signed license payloads (Ed25519)."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_log = logging.getLogger(__name__)

PREFIX = "nexa_lic_v1"


def _b64url_decode(raw: str) -> bytes:
    pad = "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode((raw + pad).encode("ascii"))


def verify_license_token(raw: str, *, public_key_pem: str | None) -> dict[str, Any] | None:
    """
    Verify ``nexa_lic_v1.<b64url(json)>.<b64url(sig)>`` signed over UTF-8 JSON bytes.

    Returns parsed payload dict or ``None`` if invalid / unsigned / verification disabled.
    """
    if not (raw or "").strip():
        return None
    pem = (public_key_pem or "").strip()
    if not pem:
        return None

    parts = raw.strip().split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        return None
    try:
        payload_bytes = _b64url_decode(parts[1])
        sig = _b64url_decode(parts[2])
        data = json.loads(payload_bytes.decode("utf-8"))
        if not isinstance(data, dict):
            return None
    except (json.JSONDecodeError, OSError, ValueError, UnicodeDecodeError) as e:
        _log.debug("license parse failed: %s", e)
        return None

    try:
        pub = serialization.load_pem_public_key(pem.encode("utf-8"))
        if not isinstance(pub, Ed25519PublicKey):
            _log.warning("license public key is not Ed25519")
            return None
        pub.verify(sig, payload_bytes)
    except Exception as e:  # noqa: BLE001
        _log.info("license verify failed: %s", e)
        return None

    return data


__all__ = ["PREFIX", "verify_license_token"]
