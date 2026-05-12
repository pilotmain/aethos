# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Split long memory text into overlapping chunks for vector recall (Phase 15)."""

from __future__ import annotations


def chunk_text(text: str, *, max_chars: int = 800, overlap: int = 100) -> list[str]:
    """
    Greedy character chunks with overlap.

    Empty input yields no chunks; whitespace-only yields [].
    """
    raw = (text or "").strip()
    if not raw:
        return []
    if max_chars < 64:
        max_chars = 64
    overlap = max(0, min(overlap, max_chars // 2))

    out: list[str] = []
    i = 0
    n = len(raw)
    while i < n:
        end = min(i + max_chars, n)
        piece = raw[i:end].strip()
        if piece:
            out.append(piece)
        if end >= n:
            break
        step = max_chars - overlap
        i += step if step > 0 else max_chars
    return out


__all__ = ["chunk_text"]
