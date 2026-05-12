# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Twilio webhook request validation (X-Twilio-Signature)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from typing import Mapping

logger = logging.getLogger(__name__)


def _signing_string(url: str, post_params: Mapping[str, str]) -> str:
    # Twilio: full URL (no query) + sorted key+value pairs (keys sorted lexicographically).
    s = str(url or "").rstrip("/")
    for k in sorted(post_params.keys()):
        s += k + (post_params.get(k) or "")
    return s


def twilio_request_signature(*, url: str, post_params: Mapping[str, str], auth_token: str) -> str:
    """Base64 HMAC-SHA1 signature as sent in ``X-Twilio-Signature``."""
    mac = hmac.new(
        auth_token.encode("utf-8"),
        _signing_string(url, post_params).encode("utf-8"),
        hashlib.sha1,
    )
    return base64.b64encode(mac.digest()).decode("ascii")


def verify_twilio_signature(
    *,
    url: str,
    post_params: Mapping[str, str],
    auth_token: str,
    x_twilio_signature: str | None,
) -> bool:
    if not auth_token or not x_twilio_signature:
        return False
    expected = twilio_request_signature(url=url, post_params=post_params, auth_token=auth_token)
    try:
        return hmac.compare_digest(expected, (x_twilio_signature or "").strip())
    except (TypeError, ValueError) as e:  # noqa: BLE001
        logger.info("twilio signature compare failed: %s", e)
        return False
