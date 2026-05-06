"""Safe reads under the workspace intelligence root."""

from __future__ import annotations

from pathlib import Path

_MAX_FILE_BYTES = 128 * 1024
_ALLOWED_SUFFIX = frozenset({".md", ".json", ".txt"})


def resolve_workspace_root(raw: str | None, *, repo_root: Path) -> Path | None:
    """Return absolute directory or None if missing / not a directory."""
    s = (raw or "").strip()
    if s:
        p = Path(s).expanduser()
        if not p.is_absolute():
            p = repo_root / p
    else:
        p = repo_root / "data" / "aethos_workspace"
    try:
        p = p.resolve()
    except OSError:
        return None
    if not p.is_dir():
        return None
    return p


def _is_under_root(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def read_workspace_file(root: Path, relative_posix: str) -> str | None:
    """Read a UTF-8 text file under root; None if unsafe or missing."""
    rel = (relative_posix or "").strip().replace("\\", "/").lstrip("/")
    if not rel or ".." in Path(rel).parts:
        return None
    full = (root / rel).resolve()
    if not _is_under_root(root, full):
        return None
    if full.suffix.lower() not in _ALLOWED_SUFFIX:
        return None
    if not full.is_file():
        return None
    try:
        data = full.read_bytes()
    except OSError:
        return None
    if len(data) > _MAX_FILE_BYTES:
        data = data[:_MAX_FILE_BYTES]
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return None


def iter_workspace_files(root: Path) -> list[str]:
    """List relative POSIX paths for supported files under root."""
    out: list[str] = []
    root = root.resolve()
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _ALLOWED_SUFFIX:
            continue
        try:
            rel = path.resolve().relative_to(root).as_posix()
        except ValueError:
            continue
        if ".." in path.parts:
            continue
        out.append(rel)
    out.sort()
    return out


__all__ = [
    "iter_workspace_files",
    "read_workspace_file",
    "resolve_workspace_root",
]
