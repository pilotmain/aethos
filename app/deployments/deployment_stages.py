# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Canonical deployment lifecycle stages (OpenClaw continuity parity)."""

from __future__ import annotations

DEPLOYMENT_STAGES: tuple[str, ...] = (
    "created",
    "preflight",
    "queued",
    "building",
    "deploying",
    "verifying",
    "completed",
    "failed",
    "recovering",
    "rolling_back",
    "rolled_back",
    "cancelled",
)

TERMINAL_STAGES: frozenset[str] = frozenset(
    {"completed", "failed", "rolled_back", "cancelled"},
)

# (from_stage, to_stage) edges we allow without extra context.
_ALLOWED: frozenset[tuple[str, str]] = frozenset(
    {
        ("created", "preflight"),
        ("preflight", "queued"),
        ("queued", "building"),
        ("building", "deploying"),
        ("deploying", "verifying"),
        ("verifying", "completed"),
        ("created", "queued"),
        ("preflight", "deploying"),
        ("queued", "deploying"),
        ("building", "failed"),
        ("deploying", "failed"),
        ("verifying", "failed"),
        ("preflight", "failed"),
        ("queued", "failed"),
        ("created", "failed"),
        ("recovering", "queued"),
        ("recovering", "deploying"),
        ("recovering", "verifying"),
        ("recovering", "failed"),
        ("completed", "rolling_back"),
        ("failed", "rolling_back"),
        ("rolling_back", "rolled_back"),
        ("rolling_back", "failed"),
        # legacy / boot normalization
        ("running", "recovering"),
        ("running", "deploying"),
        ("running", "failed"),
        ("running", "completed"),
        ("pending", "created"),
        ("pending", "preflight"),
    }
)


def is_known_stage(stage: str) -> bool:
    return str(stage) in DEPLOYMENT_STAGES


def is_terminal_stage(stage: str) -> bool:
    return str(stage) in TERMINAL_STAGES


def transition_allowed(from_stage: str, to_stage: str) -> bool:
    a, b = str(from_stage or "").strip(), str(to_stage or "").strip()
    if not b:
        return False
    if a == b:
        return True
    if b == "failed":
        return a not in TERMINAL_STAGES
    return (a, b) in _ALLOWED
