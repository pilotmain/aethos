# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Phase 73b — Read-only code context provider.

Used by the proposal generator to feed relevant source slices to the LLM.
Hard guarantees:

* Paths are resolved against the **repo root** (anchored on
  ``app/core/config.py``'s parent-of-parent) and rejected if they try to
  escape via ``..`` or absolute paths outside the root.
* Only paths whose normalized form starts with one of
  ``settings.nexa_self_improvement_allowed_paths`` (comma-separated, default
  ``app/services/,app/api/routes/,docs/``) are returned. Anything else 404s.
* A small denylist always wins regardless of the allowlist:
  ``.env*``, ``app/core/secrets*``, anything matching ``credentials*``,
  ``private_key`` / ``id_rsa`` style filenames.
* Files are size-capped (``MAX_FILE_BYTES``) to avoid feeding the LLM giant
  payloads; oversized files raise :class:`ContextTooLargeError`.

The module is **purely read-only** — there is no path here that writes to
disk. That's intentional: the LLM-facing context provider must never become
a write-back surface.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 64 * 1024  # 64 KiB per file is plenty for v1 proposals

# Paths that are *always* rejected even if they fall under an allowed prefix.
# Patterns are matched against the normalized POSIX-style relative path.
_ALWAYS_DENY_RX = re.compile(
    r"(?:^|/)(?:"
    r"\.env(?:\..*|\.example)?"
    r"|app/core/secrets(?:\.py|\.json)?"
    r"|.*credentials.*"
    r"|.*private_key.*"
    r"|.*id_rsa.*"
    r"|.*\.pem"
    r"|.*\.p12"
    r"|.*\.key"
    r"|.*\.sqlite3?(?:-journal)?"
    r"|.*\.db(?:-journal)?"
    r")$",
    re.IGNORECASE,
)


class ContextError(Exception):
    """Base class for context-fetch errors that callers should map to 4xx."""


class ContextNotAllowedError(ContextError):
    """Path is not under the allowlist or hits the always-deny list."""


class ContextNotFoundError(ContextError):
    """Path exists in the allowlist but does not exist on disk."""


class ContextTooLargeError(ContextError):
    """Path is allowed and exists but exceeds ``MAX_FILE_BYTES``."""


@dataclass(frozen=True)
class CodeContext:
    """A single (path, content) pair returned by :func:`fetch_context`."""

    path: str
    content: str
    size_bytes: int


def repo_root() -> Path:
    """Return the absolute path of the repo root (``app/core/config.py``'s grandparent)."""
    # __file__ is .../aethos/app/services/self_improvement/<this module>; parents[3]
    # walks up four levels (this file -> self_improvement -> services -> app -> aethos).
    return Path(__file__).resolve().parents[3]


def parse_allowed_paths(raw: str | None) -> list[str]:
    """Split + normalize the comma-separated allowlist into POSIX-style prefixes."""
    if not raw:
        return []
    out: list[str] = []
    for chunk in str(raw).split(","):
        p = chunk.strip().replace("\\", "/").lstrip("./")
        if not p:
            continue
        if not p.endswith("/"):
            p = p + "/"
        out.append(p)
    return out


def _allowed_paths_from_settings() -> list[str]:
    settings = get_settings()
    raw = getattr(settings, "nexa_self_improvement_allowed_paths", "") or ""
    return parse_allowed_paths(raw) or [
        "app/services/",
        "app/api/routes/",
        "docs/",
    ]


def normalize_relpath(path: str) -> str:
    """Normalize a candidate path to a POSIX-style repo-relative form.

    Raises :class:`ContextNotAllowedError` for absolute paths, ``..`` escapes,
    or paths that resolve outside the repo root.
    """
    if not path or not isinstance(path, str):
        raise ContextNotAllowedError("empty_path")
    candidate = path.strip().replace("\\", "/")
    if candidate.startswith("/"):
        raise ContextNotAllowedError("absolute_path_not_allowed")
    # Reject obvious traversal up-front (covers ``foo/../bar`` and ``../foo``).
    parts = [p for p in candidate.split("/") if p]
    if any(p == ".." for p in parts):
        raise ContextNotAllowedError("path_traversal_not_allowed")
    norm = os.path.normpath(os.path.join(*parts) if parts else "")
    norm = norm.replace(os.sep, "/")
    if norm in {"", ".", ".."}:
        raise ContextNotAllowedError("empty_path")
    if norm.startswith("/") or ".." in norm.split("/"):
        raise ContextNotAllowedError("path_traversal_not_allowed")
    return norm


def is_path_allowed(path: str) -> bool:
    """Return True iff ``path`` is under the allowlist and not in the deny list."""
    try:
        norm = normalize_relpath(path)
    except ContextNotAllowedError:
        return False
    if _ALWAYS_DENY_RX.search(norm):
        return False
    allowed = _allowed_paths_from_settings()
    return any(norm.startswith(prefix) for prefix in allowed)


def fetch_context(path: str) -> CodeContext:
    """
    Read a single file from the repo, enforcing the allowlist + deny list.

    :raises ContextNotAllowedError: path violates allowlist / deny list.
    :raises ContextNotFoundError:   path passes the rules but is missing on disk.
    :raises ContextTooLargeError:   file exceeds ``MAX_FILE_BYTES``.
    """
    norm = normalize_relpath(path)
    if _ALWAYS_DENY_RX.search(norm):
        raise ContextNotAllowedError(f"deny_list:{norm}")
    allowed = _allowed_paths_from_settings()
    if not any(norm.startswith(prefix) for prefix in allowed):
        raise ContextNotAllowedError(f"not_in_allowlist:{norm}")
    full = (repo_root() / norm).resolve()
    # Defense in depth: confirm the resolved path stays inside the repo root.
    try:
        full.relative_to(repo_root())
    except ValueError as exc:
        raise ContextNotAllowedError("resolved_outside_repo_root") from exc
    if not full.is_file():
        raise ContextNotFoundError(f"missing:{norm}")
    size = full.stat().st_size
    if size > MAX_FILE_BYTES:
        raise ContextTooLargeError(f"oversize:{norm}:{size}>{MAX_FILE_BYTES}")
    try:
        content = full.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ContextNotFoundError(f"read_failed:{norm}:{exc}") from exc
    return CodeContext(path=norm, content=content, size_bytes=size)


__all__ = [
    "CodeContext",
    "ContextError",
    "ContextNotAllowedError",
    "ContextNotFoundError",
    "ContextTooLargeError",
    "MAX_FILE_BYTES",
    "fetch_context",
    "is_path_allowed",
    "normalize_relpath",
    "parse_allowed_paths",
    "repo_root",
]
