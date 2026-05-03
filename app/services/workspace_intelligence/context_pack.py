"""Token-budget assembly for workspace file snippets."""

from __future__ import annotations

from pathlib import Path

from app.services.workspace_intelligence.loader import read_workspace_file
from app.services.workspace_intelligence.schema import WorkspaceContextPack


def _estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars per token) without model calls."""
    return max(1, len(text) // 4)


def build_pack(
    root: Path,
    ordered_relative_paths: list[str],
    *,
    max_tokens: int,
    skills: list[str],
) -> WorkspaceContextPack:
    """
    Concatenate files in order until ``max_tokens`` (estimated) is reached.

    Drops trailing files that would exceed budget; never loads GPU/embeddings.
    """
    hard_cap_chars = max_tokens * 4
    chunks: list[str] = []
    used: list[str] = []
    contents: dict[str, str] = {}
    total_chars = 0

    for rel in ordered_relative_paths:
        body = read_workspace_file(root, rel)
        if body is None:
            continue
        snippet = body.strip()
        if not snippet:
            continue
        header = f"### {rel}\n"
        block = header + snippet + "\n\n"
        if total_chars + len(block) > hard_cap_chars:
            remain = hard_cap_chars - total_chars - len(header)
            if remain < 120:
                break
            block = header + snippet[:remain].rstrip() + "\n…[trimmed]\n\n"
        chunks.append(block)
        used.append(rel)
        contents[rel] = snippet[:8000]
        total_chars += len(block)
        if total_chars >= hard_cap_chars:
            break

    summary = "".join(chunks).strip()
    return WorkspaceContextPack(
        files=used,
        file_contents=contents,
        skills=list(dict.fromkeys(skills)),
        summary=summary,
        token_estimate=_estimate_tokens(summary),
    )


__all__ = ["build_pack", "_estimate_tokens"]
