# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Provenance for external vs user-origin instructions.

Privileged host actions must not be driven solely by untrusted content (prompt injection).
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class InstructionSource(str, Enum):
    USER_MESSAGE = "user_message"
    INTERNAL_SYSTEM = "internal_system"
    UPLOADED_FILE = "uploaded_file"
    PASTED_BLOB = "pasted_blob"
    WEB_PAGE = "web_page"
    EMAIL = "email"
    DOCUMENT = "document"
    SKILL_OUTPUT = "skill_output"
    MODEL_SUMMARY = "model_summary"


UNTRUSTED_SOURCES: frozenset[str] = frozenset(
    {
        InstructionSource.UPLOADED_FILE.value,
        InstructionSource.PASTED_BLOB.value,
        InstructionSource.WEB_PAGE.value,
        InstructionSource.EMAIL.value,
        InstructionSource.DOCUMENT.value,
        InstructionSource.SKILL_OUTPUT.value,
        InstructionSource.MODEL_SUMMARY.value,
    }
)

# Subset of host actions that never run from untrusted-only provenance (all are privileged).
_PRIVILEGED_HOST_ACTIONS: frozenset[str] = frozenset(
    {
        "git_status",
        "git_commit",
        "git_push",
        "run_command",
        "file_read",
        "file_write",
        "list_directory",
        "find_files",
        "read_multiple_files",
        "vercel_projects_list",
        "vercel_remove",
        "chain",
    }
)


def apply_trusted_instruction_source(payload: dict[str, Any], source: str) -> dict[str, Any]:
    """Overwrite instruction provenance at a trust boundary (do not rely on upstream payload)."""
    out = dict(payload)
    out["instruction_source"] = normalize_instruction_source(source)
    return out


def normalize_instruction_source(raw: Any) -> str:
    s = (str(raw).strip().lower() if raw is not None else "") or InstructionSource.USER_MESSAGE.value
    for e in InstructionSource:
        if s == e.value:
            return e.value
    return InstructionSource.USER_MESSAGE.value


def enforce_instruction_source_for_host(payload: dict[str, Any]) -> None:
    """
    Block privileged host execution when the only stated origin is untrusted content.

    Chat-derived NLP (`user_message`) may still request risky paths — separate permission gates apply.
    """
    src = normalize_instruction_source(payload.get("instruction_source"))
    if src not in UNTRUSTED_SOURCES:
        return
    action = (payload.get("host_action") or payload.get("action") or "").strip().lower()
    if action in _PRIVILEGED_HOST_ACTIONS:
        raise ValueError(
            "Privileged host actions cannot be triggered from untrusted content alone. "
            "Ask in your own words in chat, or confirm after reviewing what will run."
        )
