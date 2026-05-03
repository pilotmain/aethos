"""
Enrich PATH for worker processes so user-installed CLIs resolve (Homebrew, standard UNIX dirs).

Nexa's API/worker may inherit a minimal PATH; prepend common locations while keeping the process env.
"""

from __future__ import annotations

import os
import shutil


def cli_environ_for_operator() -> dict[str, str]:
    """Full inherited env with PATH prefixed by typical CLI locations."""
    env = dict(os.environ)
    extra_dirs = [
        "/usr/local/bin",
        "/usr/bin",
        "/bin",
        "/opt/homebrew/bin",
        "/opt/homebrew/sbin",
        "/snap/bin",
    ]
    cur = env.get("PATH", "")
    env["PATH"] = os.pathsep.join(extra_dirs + ([cur] if cur else []))
    return env


def which_operator_cli(name: str) -> str | None:
    """Resolve ``name`` on the enriched PATH (same resolution subprocess.run uses)."""
    path = cli_environ_for_operator().get("PATH")
    return shutil.which(name, path=path)


__all__ = ["cli_environ_for_operator", "which_operator_cli"]
