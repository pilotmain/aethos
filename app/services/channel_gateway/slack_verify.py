# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Verify Slack Events API / Interactivity requests (signing secret v0)."""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Mapping

# Slack rejects requests older than 5 minutes (replay protection).
_MAX_SKEW_SEC = 60 * 5


def verify_slack_signature(
    *,
    signing_secret: str,
    request_timestamp: str | None,
    raw_body: bytes,
    slack_signature: str | None,
) -> bool:
    if not signing_secret or not slack_signature or not request_timestamp:
        return False
    try:
        ts = int(str(request_timestamp).strip())
    except (TypeError, ValueError):
        return False
    if abs(int(time.time()) - ts) > _MAX_SKEW_SEC:
        return False
    basestring = b"v0:" + str(ts).encode("utf-8") + b":" + raw_body
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        basestring,
        hashlib.sha256,
    ).hexdigest()
    expected = f"v0={digest}"
    return hmac.compare_digest(expected, slack_signature.strip())


def slack_sig_headers(headers: Mapping[str, str]) -> tuple[str | None, str | None]:
    """Normalize Slack signing headers (case-insensitive keys)."""
    low = {k.lower(): v for k, v in headers.items()}
    return low.get("x-slack-request-timestamp"), low.get("x-slack-signature")
