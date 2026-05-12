# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DevTaskProfile:
    task_type: str
    risk_level: str
    complexity: str
    touches_code: bool
    needs_tests: bool
    preferred_mode: str
    reason: str


def classify_dev_task(text: str) -> DevTaskProfile:
    t = (text or "").lower()

    low_risk_words = ["readme", "comment", "typo", "copy", "docs", "documentation"]
    test_words = ["test", "pytest", "failing", "failure", "regression"]
    infra_words = [
        "docker",
        "deploy",
        "env",
        "database",
        "migration",
        "auth",
        "security",
    ]
    large_words = [
        "architecture",
        "refactor",
        "rewrite",
        "redesign",
        "new feature",
        "build mvp",
    ]

    if any(w in t for w in infra_words):
        return DevTaskProfile(
            task_type="infra_or_sensitive",
            risk_level="high",
            complexity="medium",
            touches_code=True,
            needs_tests=True,
            preferred_mode="ide_handoff",
            reason="Infrastructure, auth, database, deployment, or security changes need more visibility.",
        )

    if any(w in t for w in large_words):
        return DevTaskProfile(
            task_type="large_change",
            risk_level="medium",
            complexity="high",
            touches_code=True,
            needs_tests=True,
            preferred_mode="ide_handoff",
            reason="Large changes are better reviewed in an IDE handoff first.",
        )

    if any(w in t for w in test_words):
        return DevTaskProfile(
            task_type="test_or_failure",
            risk_level="medium",
            complexity="medium",
            touches_code=True,
            needs_tests=True,
            preferred_mode="autonomous_cli",
            reason="Test/failure work can usually run through the autonomous loop with review.",
        )

    if any(w in t for w in low_risk_words):
        return DevTaskProfile(
            task_type="small_safe_change",
            risk_level="low",
            complexity="low",
            touches_code=True,
            needs_tests=False,
            preferred_mode="autonomous_cli",
            reason="Small docs/comment changes are safe for autonomous execution.",
        )

    return DevTaskProfile(
        task_type="general_dev_task",
        risk_level="normal",
        complexity="medium",
        touches_code=True,
        needs_tests=True,
        preferred_mode="autonomous_cli",
        reason="Defaulting to autonomous execution with review.",
    )
