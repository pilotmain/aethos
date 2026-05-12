# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Nexa-facing entry points for behavior composition (wraps legacy helpers; Phase 51)."""

from __future__ import annotations

from app.services.legacy_behavior_utils import build_response as compose_nexa_response
from app.services.legacy_behavior_utils import map_intent_to_behavior as map_intent_to_nexa_behavior

__all__ = ["compose_nexa_response", "map_intent_to_nexa_behavior"]
