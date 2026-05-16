# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from enum import Enum


class PrivacyMode(str, Enum):
    """Runtime privacy posture (additive; default observe — log/detect, no payload mutation)."""

    OFF = "off"
    OBSERVE = "observe"
    REDACT = "redact"
    BLOCK = "block"
    LOCAL_ONLY = "local_only"
