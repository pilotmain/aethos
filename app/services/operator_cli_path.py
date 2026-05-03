"""
Enrich PATH for worker processes so user-installed CLIs resolve.

Prepends nvm-managed Node bins (~/.nvm/versions/node/*/bin), optional VOLTA_HOME,
``~/.local/bin``, and standard UNIX/Homebrew dirs before the process PATH.
Interactive shells often add nvm/fnm paths; worker processes need the same visibility.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _effective_home() -> Path:
    """Prefer ``HOME`` (matches login shells and test isolation); fall back to ``Path.home()``."""
    raw = (os.environ.get("HOME") or "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home()


def _nvm_node_bin_directories(*, home: Path | None = None) -> list[str]:
    """Return ``bin`` dirs under nvm-style installs (deduped, NVM_BIN first, then newest-looking versions)."""
    out: list[str] = []
    seen: set[str] = set()

    nvm_bin = (os.environ.get("NVM_BIN") or "").strip()
    if nvm_bin:
        p = Path(nvm_bin).expanduser()
        if p.is_file():
            d = str(p.parent.resolve())
            if d not in seen:
                seen.add(d)
                out.append(d)

    roots: list[Path] = []
    seen_root: set[str] = set()

    def _add_root(p: Path) -> None:
        try:
            key = str(p.resolve())
        except OSError:
            return
        if key not in seen_root:
            seen_root.add(key)
            roots.append(p)

    nvm_dir = (os.environ.get("NVM_DIR") or "").strip()
    if nvm_dir:
        _add_root(Path(nvm_dir).expanduser())
    hm = home if home is not None else _effective_home()
    _add_root(hm / ".nvm")

    for root in roots:
        vn = root / "versions" / "node"
        if not vn.is_dir():
            continue
        try:
            versions = sorted(vn.iterdir(), key=lambda x: x.name, reverse=True)
        except OSError:
            continue
        for vdir in versions:
            b = vdir / "bin"
            if not b.is_dir():
                continue
            s = str(b.resolve())
            if s not in seen:
                seen.add(s)
                out.append(s)
    return out


def _volta_bin_directory() -> str | None:
    raw = (os.environ.get("VOLTA_HOME") or "").strip()
    if not raw:
        return None
    b = Path(raw).expanduser() / "bin"
    return str(b.resolve()) if b.is_dir() else None


def _user_local_bin(home: Path | None = None) -> str | None:
    hm = home if home is not None else _effective_home()
    p = hm / ".local" / "bin"
    return str(p.resolve()) if p.is_dir() else None


def _prefix_path_directories() -> list[str]:
    """Ordered prepended PATH segments (user tools before system)."""
    home = _effective_home()
    parts: list[str] = []
    seen: set[str] = set()

    def _add(d: str | None) -> None:
        if not d:
            return
        if d not in seen:
            seen.add(d)
            parts.append(d)

    for d in _nvm_node_bin_directories(home=home):
        _add(d)

    _add(_volta_bin_directory())

    _add(_user_local_bin(home=home))

    for d in (
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/opt/homebrew/bin",
        "/opt/homebrew/sbin",
        "/snap/bin",
    ):
        _add(d)

    return parts


def cli_environ_for_operator() -> dict[str, str]:
    """Full inherited env with PATH prefixed by user CLIs (nvm, Volta, ~/.local/bin) + system dirs."""
    env = dict(os.environ)
    prefix = _prefix_path_directories()
    cur = env.get("PATH", "")
    env["PATH"] = os.pathsep.join(prefix + ([cur] if cur else []))
    return env


def which_operator_cli(name: str) -> str | None:
    """Resolve ``name`` on the enriched PATH (same resolution subprocess.run uses)."""
    path = cli_environ_for_operator().get("PATH")
    return shutil.which(name, path=path)


__all__ = ["cli_environ_for_operator", "which_operator_cli"]
