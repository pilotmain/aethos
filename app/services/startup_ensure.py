# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Runtime self-heal: ensure NEXA_SECRET_KEY, print env validation, optional .venv notice.
No secrets in logs. Used by API and Telegram bot on startup.
"""
from __future__ import annotations

import logging
import os
import re
import secrets
from pathlib import Path

from dotenv import load_dotenv

from app.core.config import ENV_FILE_PATH, REPO_ROOT, get_settings

logger = logging.getLogger(__name__)


def _in_container() -> bool:
    return Path("/.dockerenv").is_file()


def _env_file_has_nexa_secret(p: Path) -> bool:
    if not p.is_file():
        return False
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(
            r"^NEXA_SECRET_KEY\s*=\s*(\S+)\s*",
            line,
        )
        if m:
            val = (m.group(1) or "").strip().strip('"').strip("'")
            return len(val) >= 8
    return False


def ensure_nexa_secret_key() -> bool:
    """
    If NEXA_SECRET_KEY is missing or too short in .env, generate one and append.
    Reloads dotenv and clears settings cache. Returns True if a key was written to disk
    (or a minimal .env was created).
    """
    p = ENV_FILE_PATH
    if p.is_file() and _env_file_has_nexa_secret(p):
        return False
    if p.is_file():
        with open(p, "a", encoding="utf-8") as f:
            f.write(
                "\n# Auto-added: server secret (BYOK); do not log this file.\n"
                f"NEXA_SECRET_KEY={_generate_secret()}\n"
            )
        print(
            "Nexa: appended NEXA_SECRET_KEY to .env. Add TELEGRAM_BOT_TOKEN if needed. "
            "The new secret is not shown here.",
            flush=True,
        )
    elif p.parent.is_dir():
        p.write_text(
            "# Minimal .env (auto). Run python scripts/nexa_bootstrap.py for the full template.\n"
            f"NEXA_SECRET_KEY={_generate_secret()}\n",
            encoding="utf-8",
        )
        print(
            "Nexa: created minimal .env with NEXA_SECRET_KEY. Run python scripts/nexa_bootstrap.py "
            "or copy env.docker.example, then set TELEGRAM_BOT_TOKEN. "
            "The new secret is not shown here.\n",
            flush=True,
        )
    else:
        os.environ["NEXA_SECRET_KEY"] = _generate_secret()
        print(
            "Nexa: NEXA_SECRET_KEY set in-process only (no writable .env in project root). "
            "For persistent BYOK, run: python scripts/nexa_bootstrap.py",
            flush=True,
        )
    load_dotenv(p, override=True) if p.is_file() else None
    get_settings.cache_clear()
    return True


def _generate_secret() -> str:
    return secrets.token_urlsafe(40)


def print_env_validation_at_startup(component: str) -> None:
    from app.services.env_validator import collect_env_validation_issues, format_env_validation_report

    try:
        issues = collect_env_validation_issues()
    except (OSError, TypeError) as e:
        logger.info("env_validation skipped: %s", e)
        return
    t = format_env_validation_report()
    if not issues:
        print(f"Nexa ({component}): {t}\n", flush=True)
        return
    print(f"Nexa ({component}) — configuration warnings (see also /dev doctor in Telegram):\n{t}\n", flush=True)
    for iss in issues[:3]:
        if "psycopg2" in (iss or "").lower() or "import" in (iss or "").lower():
            print("  Hint: pip install psycopg2-binary  (in your .venv on the host)\n", flush=True)
            break
    for iss in issues[:3]:
        if "cryptograph" in (iss or "").lower():
            print("  Hint: pip install cryptography  (in your .venv on the host)\n", flush=True)
            break
    for iss in issues:
        if "PORT" in (iss or "").upper() and "POSTGRES" in (iss or "").upper():
            print("  Hint: set POSTGRES_HOST_PORT in .env to match the published port (e.g. 5434).", flush=True)
            break


def maybe_warn_missing_venv() -> None:
    if _in_container() or (os.environ.get("NEXA_NO_VENV_WARN") or "").strip() in (
        "1",
        "true",
        "yes",
    ):
        return
    v = REPO_ROOT / ".venv"
    if v.is_dir():
        return
    print(
        "Nexa: .venv not found. For a one-command host setup, run: python scripts/nexa_bootstrap.py\n"
        "      (In Docker, dependencies are in the image — this is normal.)\n",
        flush=True,
    )


def print_missing_python_modules_hint() -> None:
    missing: list[str] = []
    try:
        import cryptography  # noqa: F401, PLC0415
    except Exception:
        missing.append("pip install cryptography")
    try:
        import psycopg2  # noqa: F401, PLC0415
    except Exception:
        missing.append("pip install psycopg2-binary")
    for m in missing:
        print(f"Nexa: missing optional import — {m}  (only needed for some local scripts)\n", flush=True)
