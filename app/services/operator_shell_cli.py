"""
Run allowlisted CLIs through a login-style bash session so ``nvm.sh`` and shell rc files apply.

Argv is built only from Nexa allowlists (never from raw user text). Uses ``shlex.join`` for the
inner command and ``shlex.quote`` for cwd — no string interpolation of untrusted input.
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Binaries permitted to run via profile shell (fixed argv[0] only).
_ALLOWLIST_ARGV0: frozenset[str] = frozenset(
    {"vercel", "gh", "git", "railway", "npm", "pnpm", "yarn", "node", "corepack"}
)


def profile_shell_enabled() -> bool:
    try:
        from app.core.config import get_settings

        return bool(getattr(get_settings(), "nexa_operator_cli_profile_shell", True))
    except Exception:  # noqa: BLE001
        return True


def run_allowlisted_argv_via_login_shell(
    argv: list[str],
    *,
    cwd: str | None,
    timeout: float,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Execute ``argv`` under ``bash -lc`` after sourcing ``nvm.sh`` and common rc files.

    Returns a dict shaped like other operator CLI helpers: ok, stdout, stderr, exit_code, error.
    """
    if not argv or (argv[0] or "").strip() not in _ALLOWLIST_ARGV0:
        return {
            "ok": False,
            "error": "argv_not_allowlisted",
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }

    workdir = cwd or os.getcwd()
    quoted_cwd = shlex.quote(workdir)
    inner = shlex.join(argv)

    # bash -lc: login bash reads /etc/profile + ~/.bash_profile etc.; then we explicitly load nvm
    # and user rc files (non-interactive workers skip Terminal.app's interactive PATH).
    script = f"""set +e
export NVM_DIR="${{NVM_DIR:-$HOME/.nvm}}"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"
[ -f "$HOME/.zprofile" ] && . "$HOME/.zprofile" 2>/dev/null || true
[ -f "$HOME/.zshrc" ] && . "$HOME/.zshrc" 2>/dev/null || true
[ -f "$HOME/.bash_profile" ] && . "$HOME/.bash_profile" 2>/dev/null || true
[ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc" 2>/dev/null || true
[ -f "$HOME/.profile" ] && . "$HOME/.profile" 2>/dev/null || true
cd {quoted_cwd} || exit 127
{inner}
exit $?
"""
    run_env = dict(env) if env is not None else os.environ.copy()
    # Ensure HOME is set for nvm/rc resolution when the worker stripped it.
    if not (run_env.get("HOME") or "").strip():
        run_env["HOME"] = str(Path.home())

    try:
        # ``-l``: login shell (profile); ``-c``: run script body (same idea as ``bash -l -c``).
        proc = subprocess.run(
            ["/bin/bash", "-lc", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=run_env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "stdout": "", "stderr": "", "exit_code": -1}
    except OSError as exc:
        logger.warning("operator_shell_cli spawn failed argv0=%s err=%s", argv[:1], type(exc).__name__)
        return {
            "ok": False,
            "error": str(exc),
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    code = int(proc.returncode)
    return {
        "ok": code == 0,
        "exit_code": code,
        "stdout": out,
        "stderr": err,
    }


__all__ = ["profile_shell_enabled", "run_allowlisted_argv_via_login_shell"]
