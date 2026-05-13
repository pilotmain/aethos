# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""ASCII-only ``NEXA_WEB_API_TOKEN`` values safe for HTTP ``Authorization`` headers."""

from __future__ import annotations

import secrets
import string

_ALPHABET = string.ascii_letters + string.digits + "-_"


def generate_web_api_token(length: int = 32) -> str:
    """
    Return a cryptographically random token using only ``A-Za-z0-9`` plus ``-`` and ``_``.

    Avoids URL-safe base64 (and any non-Latin / non-ASCII) so browsers and intermediaries
    do not reject the bearer value.
    """
    if length < 16:
        raise ValueError("length must be at least 16")
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


__all__ = ["generate_web_api_token"]
