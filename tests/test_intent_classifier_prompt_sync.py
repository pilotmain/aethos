# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Production intent prompt stays aligned with shared benchmark few-shots."""

from __future__ import annotations

from app.services.intent_classifier import INTENT_CLASSIFIER_SYSTEM
from app.services.intent_classifier_prompt_shots import INTENT_CLASSIFIER_PROMPT_SHOTS


def test_intent_classifier_system_includes_shared_shots() -> None:
    assert INTENT_CLASSIFIER_PROMPT_SHOTS in INTENT_CLASSIFIER_SYSTEM
    assert "postmortem this outage summary" in INTENT_CLASSIFIER_SYSTEM
    assert "ship the patch, update the changelog, and tag the release" in INTENT_CLASSIFIER_SYSTEM
