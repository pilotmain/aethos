"""Path checks against configured workspace roots."""

from __future__ import annotations

from pathlib import Path


def assert_workspace_path(path: str | Path, *, roots: list[str] | None = None) -> Path:
    """
    Resolve ``path`` and ensure it falls under one of ``roots`` (absolute).

    Raises ``ValueError`` if outside all roots.
    """
    p = Path(path).expanduser().resolve()
    if not roots:
        raise ValueError("no workspace roots configured")
    for r in roots:
        root = Path(r).expanduser().resolve()
        try:
            p.relative_to(root)
            return p
        except ValueError:
            continue
    raise ValueError(f"path outside workspace allowlist: {p}")


__all__ = ["assert_workspace_path"]
