"""
Guided CLI login copy for operator flows when Vercel / GitHub CLI are installed but not authenticated.

Templates never include secrets. Docker commands use ``NEXA_OPERATOR_GUIDANCE_DOCKER_CONTAINER`` (default ``nexa-api``).
"""

from __future__ import annotations

import os
from typing import Any

_VERCEL_LOGIN_HINTS = (
    "no existing credentials",
    "no-credentials-found",
    "please run `vercel login`",
    "please run vercel login",
    "not authenticated",
    "err.sh/vercel/no-credentials",
)

_GH_LOGIN_HINTS = (
    "you are not logged",
    "not logged into any github",
    "not logged in",
    "authentication required",
    "run: gh auth login",
)


def guidance_docker_container_name() -> str:
    """Container name shown in ``docker exec -it …`` examples (Cosmetic; override per deployment)."""
    env_override = (os.environ.get("NEXA_OPERATOR_GUIDANCE_DOCKER_CONTAINER") or "").strip()
    if env_override:
        return env_override
    try:
        from app.core.config import get_settings

        s = getattr(get_settings(), "nexa_operator_guidance_docker_container", None)
        if s and str(s).strip():
            return str(s).strip()
    except Exception:  # noqa: BLE001
        pass
    return "nexa-api"


def auth_guidance_enabled() -> bool:
    try:
        from app.core.config import get_settings

        return bool(getattr(get_settings(), "nexa_operator_cli_auth_guidance", True))
    except Exception:  # noqa: BLE001
        return True


def detect_vercel_auth_needed(*, ok: bool, stderr: str, stdout: str) -> bool:
    """True when ``vercel`` ran but failure looks like missing/expired login (not missing binary)."""
    if ok:
        return False
    blob = f"{stderr}\n{stdout}".lower()
    return any(h in blob for h in _VERCEL_LOGIN_HINTS)


def detect_github_auth_needed(*, ok: bool, stderr: str, stdout: str, exit_code: int) -> bool:
    """True when ``gh auth status`` indicates no usable GitHub login."""
    if ok:
        return False
    blob = f"{stderr}\n{stdout}".lower()
    if exit_code == 0:
        return False
    return any(h in blob for h in _GH_LOGIN_HINTS)


def markdown_vercel_login_guidance() -> str:
    c = guidance_docker_container_name()
    return f"""### Vercel authentication required

The CLI ran but **is not logged in** (or the session expired).

**One-time setup (Docker)** — run on your Mac terminal:

1. `docker exec -it {c} vercel login`
2. Verify: `docker exec -it {c} vercel whoami`

**Host (no Docker):** run `vercel login` in your terminal, then retry.

**Token fallback (optional):** create a token at [Vercel tokens](https://vercel.com/account/tokens) and set `VERCEL_TOKEN` in the environment that runs the worker (not in chat).

Reply **done** after login so we can retry."""


def markdown_github_login_guidance() -> str:
    c = guidance_docker_container_name()
    return f"""### GitHub CLI authentication required

`gh` is installed but **not logged in**.

**One-time setup (Docker):**

1. `docker exec -it {c} gh auth login` (HTTPS + browser, or follow prompts)
2. Verify: `docker exec -it {c} gh auth status`

**Device / web flow:** `docker exec -it {c} gh auth login --web`

**Token fallback:** set `GITHUB_TOKEN` or `GH_TOKEN` in the worker environment (never paste into Telegram).

Reply **done** after login."""


def append_guidance_if_needed_vercel(body: str, whoami: dict[str, Any]) -> str:
    if not auth_guidance_enabled():
        return body
    if whoami.get("error") == "vercel_cli_missing":
        return body
    stderr = str(whoami.get("stderr") or "")
    stdout = str(whoami.get("stdout") or "")
    ok = bool(whoami.get("ok"))
    if not detect_vercel_auth_needed(ok=ok, stderr=stderr, stdout=stdout):
        return body
    return body.rstrip() + "\n\n" + markdown_vercel_login_guidance()


def append_guidance_if_needed_github(body: str, auth: dict[str, Any]) -> str:
    if not auth_guidance_enabled():
        return body
    if auth.get("error") == "gh_cli_missing":
        return body
    stderr = str(auth.get("stderr") or "")
    stdout = str(auth.get("stdout") or "")
    ok = bool(auth.get("ok"))
    code = int(auth.get("exit_code") if auth.get("exit_code") is not None else (0 if ok else 1))
    if not detect_github_auth_needed(ok=ok, stderr=stderr, stdout=stdout, exit_code=code):
        return body
    return body.rstrip() + "\n\n" + markdown_github_login_guidance()


__all__ = [
    "append_guidance_if_needed_github",
    "append_guidance_if_needed_vercel",
    "auth_guidance_enabled",
    "detect_github_auth_needed",
    "detect_vercel_auth_needed",
    "guidance_docker_container_name",
    "markdown_github_login_guidance",
    "markdown_vercel_login_guidance",
]
