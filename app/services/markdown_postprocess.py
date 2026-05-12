# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Lightweight cleanup for LLM/agent Markdown artifacts (no full parser)."""

from __future__ import annotations

import re


def clean_agent_markdown_output(text: str) -> str:
    """
    Remove dangling ``**`` markers common in numbered lists, e.g.
    ``1. Cost Reduction** — note`` → ``1. Cost Reduction — note``.
    """
    if not text or "**" not in text:
        return text
    # Numbered list: title accidentally closed with ** before em dash or hyphen
    out = re.sub(
        r"(^|\n)(\s*\d+\.\s+[^\n]+?)\*\*(\s*[—\-]\s)",
        r"\1\2\3",
        text,
        flags=re.MULTILINE,
    )
    return out
