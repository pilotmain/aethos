# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Heuristics for 'export this' style chat (Telegram and future web)."""

from __future__ import annotations

import re


def detect_natural_export_format(text: str) -> str | None:
    """Return pdf | docx | md | txt when the user is clearly asking to export, else None."""
    t = (text or "").strip()
    if not t or t.startswith("/"):
        return None
    low = t.lower()
    exportish = any(
        x in low
        for x in (
            "export",
            "download this",
            "as a pdf",
            "as pdf",
            "as word",
            "as a word",
            "as docx",
            "as markdown",
            "as plain text",
            "make this a",
            "make a pdf",
            "make a word",
            "turn this into a",
            "turn this into",
            "client-ready",
            "save as",
        )
    )
    if not exportish:
        return None
    if re.search(r"\b(docx?|ms word|word document)\b", low):
        return "docx"
    if re.search(r"\b(pdf)\b", low) or re.search(r"\bdoc\s*pdf\b", low):
        return "pdf"
    if "markdown" in low or re.search(r"\b\.md\b", t):
        return "md"
    if "plain text" in low or re.search(r"\b\.txt\b", t) or re.search(
        r"\bas text\b", low
    ):
        return "txt"
    if re.search(
        r"\b(export|download|document|file)\b", low
    ) and "this" in low and not re.search(
        r"\b(pdf|word|docx|markdown|text|txt)\b", low
    ):
        return "pdf"
    if "pdf" in low:
        return "pdf"
    if "word" in low and "password" not in low:
        return "docx"
    return "pdf" if exportish else None
