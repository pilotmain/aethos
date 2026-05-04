"""
Run allowlisted CLIs through the user's login shell so ``nvm.sh`` and rc files apply like Terminal/Cursor.

Uses ``$SHELL`` when executable (typically ``/bin/zsh`` on macOS), else falls back to ``/bin/zsh``,
then ``/bin/bash``. Argv is built only from Nexa allowlists — never raw user shell strings.
"""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from app.services.cli_backends import get_cli_command, operator_abs_debug_enabled

logger = logging.getLogger(__name__)

# Binaries permitted to run via profile shell (fixed argv[0] only).
_ALLOWLIST_ARGV0: frozenset[str] = frozenset(
    {"vercel", "gh", "git", "railway", "npm", "pnpm", "yarn", "node", "corepack"}
)


def _synchronized_path_export(run_env: dict[str, str]) -> str:
    """
    Re-apply the same PATH Nexa built in Python as the first line of the -c script.

    Login/profile startup can reset PATH before this body runs; ``vercel`` (npm -g) and
    Homebrew ``gh`` then disappear unless we restore the enriched PATH and activate nvm's Node.
    """
    path = (run_env.get("PATH") or "").strip()
    if not path:
        return ""
    return f"export PATH={shlex.quote(path)}\n"


def _profile_environment_script() -> str:
    """Shell fragment: nvm + default Node (for npm globals) + completions + common rc files."""
    return """set +e
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
# Non-interactive -c scripts do not auto-select a Node version; npm global CLIs (vercel) need it.
if type nvm >/dev/null 2>&1; then
  nvm use default --silent 2>/dev/null || nvm use node --silent 2>/dev/null || nvm use --lts --silent 2>/dev/null || true
fi
[ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"
[ -f "$HOME/.zprofile" ] && . "$HOME/.zprofile" 2>/dev/null || true
[ -f "$HOME/.zshrc" ] && . "$HOME/.zshrc" 2>/dev/null || true
[ -f "$HOME/.bash_profile" ] && . "$HOME/.bash_profile" 2>/dev/null || true
[ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc" 2>/dev/null || true
[ -f "$HOME/.profile" ] && . "$HOME/.profile" 2>/dev/null || true
"""


def resolve_login_shell_executable() -> str:
    """
    Prefer ``$SHELL`` (same as Terminal/Cursor when the worker inherits user env).

    Falls back to ``/bin/zsh``, ``/bin/bash``, then ``/bin/sh``.
    """
    raw = (os.environ.get("SHELL") or "").strip()
    if raw:
        try:
            p = Path(raw).expanduser()
            if p.is_file() and os.access(p, os.X_OK):
                return str(p.resolve())
        except OSError:
            pass
    for fb in ("/bin/zsh", "/bin/bash", "/bin/sh"):
        if Path(fb).is_file():
            return fb
    return "/bin/sh"


def profile_shell_enabled() -> bool:
    try:
        from app.core.config import get_settings

        return bool(getattr(get_settings(), "nexa_operator_cli_profile_shell", True))
    except Exception:  # noqa: BLE001
        return True


def _command_v_hint(
    shell: str,
    binary: str,
    *,
    env: dict[str, str],
    timeout: float,
) -> str:
    """After the same PATH + profile sources, run ``command -v`` when the CLI run fails."""
    script = (
        _synchronized_path_export(env)
        + _profile_environment_script()
        + f"command -v {shlex.quote(binary)} 2>/dev/null\n"
    )
    try:
        proc = subprocess.run(
            [shell, "-l", "-c", script],
            capture_output=True,
            text=True,
            timeout=min(timeout, 25.0),
            env=env,
        )
        return (proc.stdout or "").strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def run_allowlisted_argv_via_login_shell(
    argv: list[str],
    *,
    cwd: str | None,
    timeout: float,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Execute ``argv`` under ``$SHELL -l -c`` (or fallback) after sourcing nvm and rc files.

    **Important:** ``argv`` is passed through :func:`~app.services.cli_backends.get_cli_command`
    *before* building the shell script body. The resolved executable (absolute path when
    configured, or PATH-resolved / bare name) is embedded with :func:`shlex.join` — there is no
    separate code path that skips CLI backend resolution for login-shell execution.

    Returns a dict shaped like other operator CLI helpers: ok, stdout, stderr, exit_code, error.
    """
    argv = list(argv)
    if argv:
        argv = get_cli_command(Path((argv[0] or "").strip()).name, list(argv[1:]))
    argv0_name = Path((argv[0] or "").strip()).name
    if not argv or argv0_name not in _ALLOWLIST_ARGV0:
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
    if operator_abs_debug_enabled():
        logger.info(
            "[operator_shell_cli] embedded inner command after CLI backend resolution: %s",
            inner[:800] + ("…" if len(inner) > 800 else ""),
        )

    run_env = dict(env) if env is not None else os.environ.copy()
    if not (run_env.get("HOME") or "").strip():
        run_env["HOME"] = str(Path.home())

    script = (
        _synchronized_path_export(run_env)
        + _profile_environment_script()
        + f"cd {quoted_cwd} || exit 127\n{inner}\nexit $?\n"
    )

    shell = resolve_login_shell_executable()

    try:
        proc = subprocess.run(
            [shell, "-l", "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout,
            env=run_env,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "timeout", "stdout": "", "stderr": "", "exit_code": -1}
    except OSError as exc:
        logger.warning("operator_shell_cli spawn failed argv0=%s shell=%s err=%s", argv[:1], shell, type(exc).__name__)
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

    if code != 0 and argv:
        hint = _command_v_hint(shell, argv0_name, env=run_env, timeout=timeout)
        if hint:
            err = (err + f"\n\n_After profile load, `command -v {argv0_name}` → `{hint}`_").strip()

    return {
        "ok": code == 0,
        "exit_code": code,
        "stdout": out,
        "stderr": err,
    }


__all__ = [
    "profile_shell_enabled",
    "resolve_login_shell_executable",
    "run_allowlisted_argv_via_login_shell",
]
