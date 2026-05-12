# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Pro model routing — symbolic tier selection (core maps to real model IDs)."""

from __future__ import annotations

from typing import Any


def choose_model(task_type: str, complexity: str, cost_budget: float) -> str:
    """
    Return a symbolic key consumed by Nexa core :func:`map_pro_routing_model_key`.

    - ``claude-strong`` — best quality for dev / hard tasks
    - ``local-ollama`` — fast/cheap path (core may still use Anthropic Haiku-class if Ollama unused)
    - ``balanced`` — default tier
    """
    tt = (task_type or "chat").strip().lower()
    cx = (complexity or "medium").strip().lower()
    if tt == "dev":
        return "claude-strong"
    if cx == "low":
        return "local-ollama"
    _ = cost_budget  # reserved for future spend-aware routing
    return "balanced"


__all__ = ["choose_model"]
