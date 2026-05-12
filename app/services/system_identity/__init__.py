# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""System identity: capability source of truth and canonical user-facing copy."""

from __future__ import annotations

from app.services.system_identity.capabilities import (
    CAPABILITIES,
    NEXA_CAPABILITY_REPLY,
    NEXA_MULTI_AGENT_CLARIFICATION,
    describe_capabilities,
    narrative_capability_answer,
)

__all__ = [
    "CAPABILITIES",
    "NEXA_CAPABILITY_REPLY",
    "NEXA_MULTI_AGENT_CLARIFICATION",
    "describe_capabilities",
    "narrative_capability_answer",
]
