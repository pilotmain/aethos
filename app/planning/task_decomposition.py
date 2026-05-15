# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Deterministic task decomposition (reuses workflow builder semantics)."""

from __future__ import annotations

from typing import Any

from app.execution import workflow_builder


def decompose_operator_text(text: str) -> list[dict[str, Any]]:
    """Return execution steps for operator text (same graph as gateway workflows)."""
    return workflow_builder.build_steps_from_operator_text(text)
