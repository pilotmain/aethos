# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Meta WhatsApp webhook POST signature (X-Hub-Signature-256)."""

from __future__ import annotations

import hashlib
import hmac


def verify_meta_webhook_signature(
    *,
    app_secret: str,
    raw_body: bytes,
    x_hub_signature_256: str | None,
) -> bool:
    """
    Verify ``X-Hub-Signature-256: sha256=<hex>`` from Meta webhooks.
    """
    if not app_secret or not x_hub_signature_256:
        return False
    sig = x_hub_signature_256.strip()
    if "=" not in sig:
        return False
    kind, digest = sig.split("=", 1)
    if kind.strip().lower() != "sha256":
        return False
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, digest.strip())
