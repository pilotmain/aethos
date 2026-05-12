#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""AethOS interactive setup wizard — first-run and re-run with backup + validation."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

# Resolve imports: ``scripts/setup_helpers`` when run as ``python scripts/setup.py``
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from setup_helpers import (  # noqa: E402
    Colors,
    HelpSystem,
    ProgressBar,
    Validator,
    backup_env_file,
)


STATE_FILE = _REPO_ROOT / ".aethos_setup_state.json"
BACKUP_SUBDIR = _REPO_ROOT / ".setup" / "backups"
TOTAL_STEPS = 9
CREDS_FILE_HOME = Path.home() / ".aethos_credentials"


def display_legal_notice(*, force: bool, accept_disclaimer: bool) -> None:
    """Show warranty / liability summary; require acknowledgment unless bypassed."""
    if (os.environ.get("AETHOS_SETUP_SKIP_LEGAL") or "").strip().lower() in ("1", "true", "yes"):
        return

    env_accept = (os.environ.get("AETHOS_SETUP_ACCEPT_DISCLAIMER") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    if force or accept_disclaimer or env_accept:
        print(
            f"\n{Colors.YELLOW}{'═' * 60}{Colors.RESET}\n"
            f"{Colors.BOLD}Legal notice{Colors.RESET}\n"
            f"{Colors.DIM}AethOS is provided AS IS without warranty. You are responsible for AI agent "
            f"actions, backups, and approvals. See {Colors.CYAN}LICENSE.disclaimer{Colors.DIM} in the repo root.{Colors.RESET}\n"
            f"{Colors.DIM}(Continuing: --force, --accept-disclaimer, or AETHOS_SETUP_ACCEPT_DISCLAIMER=1.){Colors.RESET}\n"
            f"{Colors.YELLOW}{'═' * 60}{Colors.RESET}\n"
        )
        return

    print(f"\n{Colors.YELLOW}{'═' * 60}{Colors.RESET}")
    print(f"{Colors.BOLD}Legal notice{Colors.RESET}")
    print(f"{Colors.YELLOW}{'═' * 60}{Colors.RESET}")
    print(
        """
By using AethOS, you acknowledge that:
• This software is provided "AS IS" without warranty
• You are solely responsible for AI agent actions and data backups
• Maintainer liability is limited; see LICENSE.disclaimer in the repo root
"""
    )
    print(f"{Colors.YELLOW}{'═' * 60}{Colors.RESET}\n")

    if not sys.stdin.isatty():
        print(
            Colors.error(
                "Non-interactive shell: read LICENSE.disclaimer, then set "
                "AETHOS_SETUP_ACCEPT_DISCLAIMER=1, or pass --accept-disclaimer, or use --force."
            )
        )
        sys.exit(1)

    response = prompt_line(f"{Colors.question('Do you accept these terms? (yes/no)')} ").strip().lower()
    if response not in ("yes", "y"):
        print(Colors.error("Setup cancelled. Accept the terms to continue (see LICENSE.disclaimer)."))
        sys.exit(1)


def _parse_help_argv(argv: list[str]) -> bool:
    """Handle ``--help``, ``-h``, and ``help [topic]``. Returns True if handled."""
    if not argv:
        return False
    if argv[0] in ("-h", "--help"):
        HelpSystem.show()
        return True
    if argv[0] == "help":
        HelpSystem.show(argv[1] if len(argv) > 1 else None)
        return True
    return False


def prompt_line(prompt: str) -> str:
    """Read input; ``help`` / ``?`` / ``help topic`` shows HelpSystem."""
    while True:
        raw = input(prompt)
        line = raw.strip()
        low = line.lower()
        if low in ("help", "?"):
            HelpSystem.show()
            continue
        if low.startswith("help "):
            HelpSystem.show(low[5:].strip())
            continue
        return raw


def default_sqlite_database_url() -> str:
    data_dir = Path.home() / ".aethos" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "aethos.db"
    return f"sqlite:////{db_path.resolve()}"


def parse_port_from_api_base(api_base: str) -> int:
    s = (api_base or "").strip().rstrip("/")
    if not s:
        return 8010
    try:
        part = s.rsplit(":", 1)[-1]
        return int(part.split("/")[0])
    except (ValueError, IndexError):
        return 8010


class SetupWizard:
    """Orchestrates numbered steps with persistent state for resume."""

    STEP_IDS = (
        "requirements",
        "dependencies",
        "environment",
        "authentication",
        "database",
        "llm_keys",
        "host_executor",
        "services",
        "verify",
    )

    def __init__(
        self,
        *,
        resume: bool,
        skip_services: bool,
        full_reset: bool,
        force: bool = False,
        accept_disclaimer: bool = False,
    ) -> None:
        self.repo_root = _REPO_ROOT
        self.env_path = self.repo_root / ".env"
        self.env_example = self.repo_root / ".env.example"
        self.requirements = self.repo_root / "requirements.txt"
        self.pyproject = self.repo_root / "pyproject.toml"
        self.resume = resume
        self.skip_services = skip_services
        self.full_reset = full_reset
        self.accept_disclaimer = accept_disclaimer
        env_force = (os.environ.get("AETHOS_SETUP_FORCE") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        self.force = bool(force or env_force)
        self.results: dict[str, bool] = {}
        self._api_process: subprocess.Popen[bytes] | None = None
        self.pending_workspace: tuple[str, str] | None = None
        self._workspace_register_done: bool = False

    # --- state ---

    def _load_state(self) -> dict[str, Any]:
        if not STATE_FILE.is_file():
            return {}
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_state(self) -> None:
        payload = {
            "completed_steps": [k for k, v in self.results.items() if v],
            "failed_steps": [k for k, v in self.results.items() if not v],
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # --- banner ---

    def print_banner(self) -> None:
        banner = f"""
{Colors.BOLD}{Colors.CYAN}
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║     █████╗ ███████╗████████╗██╗  ██╗ ██████╗ ███████╗        ║
    ║    ██╔══██╗██╔════╝╚══██╔══╝██║  ██║██╔═══██╗██╔════╝        ║
    ║    ███████║█████╗     ██║   ███████║██║   ██║███████╗        ║
    ║    ██╔══██║██╔══╝     ██║   ██╔══██║██║   ██║╚════██║        ║
    ║    ██║  ██║███████╗   ██║   ██║  ██║╚██████╔╝███████║        ║
    ║    ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝        ║
    ║                                                              ║
    ║              The Agentic Operating System                    ║
    ║                   Setup Wizard v1.0                          ║
    ╚══════════════════════════════════════════════════════════════╝
{Colors.RESET}
"""
        print(banner)
        print(
            f"{Colors.DIM}Type {Colors.CYAN}help{Colors.DIM} at any prompt for assistance.{Colors.RESET}\n"
        )

    # --- steps ---

    def check_requirements(self) -> bool:
        print(f"\n{Colors.step(1, TOTAL_STEPS, 'Checking system requirements…')}\n")
        checks: list[tuple[str, Callable[[], tuple[bool, str]]]] = [
            ("Python 3.9+", Validator.check_python_version),
            ("Disk space (1GB+)", lambda: Validator.check_disk_space(str(self.repo_root))),
            ("API port 8000 or 8010", Validator.check_common_api_ports),
            ("Internet (pypi.org)", self._check_internet),
            ("Git (optional)", self._check_git),
        ]
        all_passed = True
        for name, fn in checks:
            passed, msg = fn()
            line = f"{name} — {msg}"
            print(f"  {Colors.success(line)}" if passed else f"  {Colors.error(line)}")
            if not passed:
                all_passed = False
        if not all_passed:
            print(f"\n{Colors.warning('Some checks failed. You can still continue.')}")
            out = prompt_line(f"{Colors.question('Continue anyway? [y/N]')} ").strip().lower()
            return out == "y"
        return True

    def _check_internet(self) -> tuple[bool, str]:
        try:
            urllib.request.urlopen("https://pypi.org", timeout=5)
            return True, "reachable"
        except (urllib.error.URLError, OSError):
            return False, "could not reach pypi.org"

    def _check_git(self) -> tuple[bool, str]:
        try:
            subprocess.run(
                ["git", "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
            return True, "installed"
        except (OSError, subprocess.CalledProcessError):
            return False, "not found (optional)"

    def install_dependencies(self) -> bool:
        print(f"\n{Colors.step(2, TOTAL_STEPS, 'Installing dependencies…')}\n")
        if not self.requirements.is_file():
            print(f"  {Colors.warning('requirements.txt not found — skipping pip install')}")
            return True
        print(f"  {Colors.info('pip install -r requirements.txt')}")
        pb = ProgressBar(total=20, prefix="pip", suffix="")
        try:

            def _pip() -> int:
                return subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(self.requirements)],
                    cwd=str(self.repo_root),
                    capture_output=True,
                    text=True,
                    timeout=600,
                ).returncode

            code = pb.animate_while(_pip, steps=20, interval=0.15)
        except subprocess.TimeoutExpired:
            print(f"\n  {Colors.error('pip timed out')}")
            return False
        except Exception as exc:  # noqa: BLE001
            print(f"\n  {Colors.error(str(exc))}")
            return False
        if code != 0:
            print(f"  {Colors.error('pip install failed — check output above or run manually')}")
            return False
        if self.pyproject.is_file():
            print(f"  {Colors.info('pip install -e . (editable package)')}")
            r2 = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-e", "."],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=600,
            )
            if r2.returncode != 0:
                print(f"  {Colors.warning('editable install failed — API imports may still work if already installed')}")
        print(f"  {Colors.success('Dependencies installed')}")
        return True

    def configure_env(self) -> bool:
        print(f"\n{Colors.step(3, TOTAL_STEPS, 'Configuring environment…')}\n")
        if self.env_path.is_file():
            BACKUP_SUBDIR.mkdir(parents=True, exist_ok=True)
            dest = backup_env_file(self.env_path, backups_dir=BACKUP_SUBDIR)
            print(f"  {Colors.info(f'Backed up existing .env → {dest}')}")

        if self.env_example.is_file():
            import shutil

            shutil.copy(self.env_example, self.env_path)
            print(f"  {Colors.success('Created .env from .env.example')}")
        else:
            self.env_path.write_text(self._minimal_env_blob(), encoding="utf-8")
            print(f"  {Colors.success('Created minimal .env (no .env.example found)')}")

        print("\n  Critical configuration:\n")
        default_port = 8010
        while True:
            raw = prompt_line(
                f"  {Colors.question(f'API port [{default_port}]')} "
            ).strip()
            port_s = raw or str(default_port)
            try:
                port = int(port_s)
                if 1024 <= port <= 65535:
                    api_base = f"http://127.0.0.1:{port}"
                    self._update_env_key("API_BASE_URL", api_base)
                    print(f"  {Colors.success(f'API_BASE_URL={api_base}')}")
                    break
                print(f"  {Colors.error('Port must be between 1024 and 65535')}")
            except ValueError:
                print(f"  {Colors.error('Invalid port')}")

        db_choice = prompt_line(
            f"  {Colors.question('Database [sqlite/postgres] (default: sqlite)')} "
        ).strip().lower()
        if db_choice == "postgres":
            print(f"  {Colors.info('PostgreSQL — enter connection details')}")
            db_name = prompt_line(f"  {Colors.question('Database name')} ").strip()
            db_user = prompt_line(f"  {Colors.question('Username')} ").strip()
            import getpass

            db_password = getpass.getpass(f"  {Colors.CYAN}Password:{Colors.RESET} ")
            db_host = prompt_line(f"  {Colors.question('Host [localhost]')} ").strip() or "localhost"
            db_port = prompt_line(f"  {Colors.question('Port [5432]')} ").strip() or "5432"
            enc_user = urllib.parse.quote_plus(db_user)
            enc_pass = urllib.parse.quote_plus(db_password)
            db_url = f"postgresql://{enc_user}:{enc_pass}@{db_host}:{db_port}/{db_name}"
            self._update_env_key("DATABASE_URL", db_url)
            print(f"  {Colors.success('DATABASE_URL set (postgresql)')}")
        else:
            db_url = default_sqlite_database_url()
            self._update_env_key("DATABASE_URL", db_url)
            print(f"  {Colors.success(f'SQLite configured — {db_url}')}")

        sk = self._get_env_value("NEXA_SECRET_KEY")
        if not sk or sk.strip().lower() in ("change-me-in-production", "changeme"):
            new_secret = secrets.token_urlsafe(32)
            self._update_env_key("NEXA_SECRET_KEY", new_secret)
            print(f"  {Colors.success('Generated NEXA_SECRET_KEY')}")

        tok = self._get_env_value("NEXA_WEB_API_TOKEN")
        if not tok:
            wt = secrets.token_urlsafe(32)
            self._update_env_key("NEXA_WEB_API_TOKEN", wt)
            print(f"  {Colors.success('Generated NEXA_WEB_API_TOKEN (for Mission Control auth)')}")

        wr = self._get_env_value("NEXA_WORKSPACE_ROOT")
        if not wr:
            default_wr = str(Path.home() / "aethos-workspace")
            self._update_env_key("NEXA_WORKSPACE_ROOT", default_wr)
            self._update_env_key("HOST_EXECUTOR_WORK_ROOT", default_wr)
            print(f"  {Colors.info(f'Default workspace roots → {default_wr}')}")

        return True

    def _validate_setup_user_id(self, uid: str) -> tuple[bool, str]:
        """Ensure ``uid`` matches :func:`~app.services.web_user_id.validate_web_user_id`."""
        u = (uid or "").strip()[:80]
        if not u:
            return False, "User ID cannot be empty"
        try:
            sys.path.insert(0, str(self.repo_root))
            from app.services.web_user_id import validate_web_user_id

            validate_web_user_id(u)
            return True, ""
        except ValueError as e:
            return False, str(e)
        except Exception as exc:  # noqa: BLE001
            return False, f"Could not validate User ID ({exc!s}). Use e.g. web_yourname or tg_<digits>."

    def _merge_telegram_owner_ids(self, telegram_digits: str) -> None:
        cur = (self._get_env_value("TELEGRAM_OWNER_IDS") or "").strip()
        parts = {p.strip() for p in cur.replace(",", " ").split() if p.strip().isdigit()}
        parts.add(telegram_digits.strip())
        merged = ",".join(sorted(parts, key=lambda x: int(x)))
        self._update_env_key("TELEGRAM_OWNER_IDS", merged)

    def _save_credentials_file(self, user_id: str, web_token: str) -> None:
        api_base = (self._get_env_value("API_BASE_URL") or "http://127.0.0.1:8010").strip()
        port = parse_port_from_api_base(api_base)
        tg_tok = (self._get_env_value("TELEGRAM_BOT_TOKEN") or "").strip()
        lines = [
            "# AethOS credentials — generated by scripts/setup.py",
            f"# Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            f"API_URL={api_base}",
            f"API_PORT={port}",
            f"X_USER_ID={user_id}",
            f"BEARER_TOKEN={web_token}",
            "",
        ]
        if tg_tok:
            lines.append(f"TELEGRAM_BOT_TOKEN={tg_tok}")
        else:
            lines.append("# TELEGRAM_BOT_TOKEN=(not set)")
        CREDS_FILE_HOME.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def configure_authentication(self) -> bool:
        """Collect Mission Control user id, optional Telegram token, display bearer token."""
        print(f"\n{Colors.step(4, TOTAL_STEPS, 'Authentication (web API)…')}\n")
        print(
            f"  {Colors.info('Mission Control requests X-User-Id + Bearer token when NEXA_WEB_API_TOKEN is set.')}"
        )
        print(
            f"  {Colors.DIM}Use a stable id you will paste into the web UI (e.g. web_yourname or tg_<Telegram digits>).{Colors.RESET}"
        )

        default_uid = f"web_setup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        while True:
            raw = prompt_line(
                f"  {Colors.question(f'X-User-Id [{default_uid}]')} "
            ).strip()
            candidate = (raw if raw else default_uid).strip()[:80]
            ok, err = self._validate_setup_user_id(candidate)
            if ok:
                user_id = candidate
                break
            print(f"  {Colors.error(err)}")
            print(
                f"  {Colors.DIM}Examples: web_alice  ·  tg_EXAMPLE0000000001{Colors.RESET}"
            )

        self._update_env_key("TEST_X_USER_ID", user_id)
        print(f"  {Colors.success(f'Saved TEST_X_USER_ID={user_id}')}")

        yn = prompt_line(
            f"  {Colors.question('Configure Telegram bot token now? [y/N]')} "
        ).strip().lower()
        if yn == "y":
            print(f"\n  {Colors.info('Open Telegram → @BotFather → /newbot — paste the token here.')}")
            bot_token = prompt_line(
                f"  {Colors.question('TELEGRAM_BOT_TOKEN (or Enter to skip)')} "
            ).strip()
            if bot_token and len(bot_token) > 20 and ":" in bot_token:
                self._update_env_key("TELEGRAM_BOT_TOKEN", bot_token)
                self._update_env_key("NEXA_TELEGRAM_EMBED_WITH_API", "true")
                print(f"  {Colors.success('Telegram bot token saved')}")
                if user_id.startswith("tg_") and user_id[3:].isdigit():
                    self._merge_telegram_owner_ids(user_id[3:])
                    print(
                        f"  {Colors.info('Merged your tg id into TELEGRAM_OWNER_IDS for owner role.')}"
                    )
            else:
                print(f"  {Colors.warning('Skipped — add TELEGRAM_BOT_TOKEN in .env later.')}")
        else:
            print(f"  {Colors.DIM}Skipping Telegram.{Colors.RESET}")

        web_token = (self._get_env_value("NEXA_WEB_API_TOKEN") or "").strip()
        if not web_token:
            web_token = secrets.token_urlsafe(32)
            self._update_env_key("NEXA_WEB_API_TOKEN", web_token)

        print(f"\n  {Colors.success('Web API bearer token (Mission Control)')}")
        print(f"  {Colors.BOLD}{Colors.CYAN}{'─' * 52}{Colors.RESET}")
        print(f"  {Colors.BOLD}NEXA_WEB_API_TOKEN{Colors.RESET}")
        print(f"  {Colors.CYAN}{web_token}{Colors.RESET}")
        print(f"  {Colors.BOLD}{Colors.CYAN}{'─' * 52}{Colors.RESET}")
        print(
            f"  {Colors.warning('Save this token — the web UI needs Authorization: Bearer <token>.')}"
        )

        self._save_credentials_file(user_id, web_token)
        print(f"  {Colors.DIM}Credentials file: {CREDS_FILE_HOME}{Colors.RESET}\n")

        return True

    def _minimal_env_blob(self) -> str:
        return f"""# AethOS — generated by scripts/setup.py
APP_NAME=AethOS
APP_ENV=development
API_BASE_URL=http://127.0.0.1:8010
DATABASE_URL={default_sqlite_database_url()}
NEXA_SECRET_KEY={secrets.token_urlsafe(32)}
NEXA_WEB_API_TOKEN={secrets.token_urlsafe(32)}
NEXA_AGENT_ORCHESTRATION_ENABLED=true
USE_REAL_LLM=false
NEXA_WORKSPACE_ROOT={Path.home() / "aethos-workspace"}
HOST_EXECUTOR_WORK_ROOT={Path.home() / "aethos-workspace"}
# TELEGRAM_BOT_TOKEN=
"""

    def configure_llm_keys(self) -> bool:
        print(f"\n{Colors.step(6, TOTAL_STEPS, 'Optional LLM API keys…')}\n")
        print(
            f"  {Colors.info('Add at least one provider for full chat/dev features (optional for offline/dev)')}"
        )
        providers: list[tuple[str, str, str | None]] = [
            ("Anthropic", "ANTHROPIC_API_KEY", "sk-ant-"),
            ("OpenAI", "OPENAI_API_KEY", "sk-"),
            ("DeepSeek", "DEEPSEEK_API_KEY", None),
        ]
        configured = 0
        for name, env_key, prefix in providers:
            cur = self._get_env_value(env_key)
            if cur and not cur.startswith("#") and len(cur.strip()) > 8:
                print(f"  {Colors.success(f'{name}: already set in .env')}")
                configured += 1
                continue
            yn = prompt_line(f"  {Colors.question(f'Configure {name} now? [y/N]')} ").strip().lower()
            if yn != "y":
                continue
            key = prompt_line(f"  {Colors.question(f'{name} API key')} ").strip()
            if not key:
                print(f"  {Colors.warning('Skipped empty key')}")
                continue
            if prefix and not key.startswith(prefix):
                print(f"  {Colors.warning(f'Unexpected prefix — storing anyway')}")
            self._update_env_key(env_key, key)
            print(f"  {Colors.success(f'{name} saved to .env')}")
            configured += 1
        if configured == 0:
            print(f"\n  {Colors.warning('No LLM keys added — you can edit .env later.')}")
        return True

    def configure_host_executor(self) -> bool:
        """Enable host executor + work root; optional workspace root registration after API is up."""
        print(f"\n{Colors.step(7, TOTAL_STEPS, 'Host executor (autonomous runs)…')}\n")
        print(
            f"  {Colors.info('Sub-agents and host jobs need NEXA_HOST_EXECUTOR_ENABLED on the worker/API host.')}"
        )
        print(
            f"  {Colors.DIM}The API process must load these env vars; restart after changing .env.{Colors.RESET}\n"
        )
        yn = prompt_line(
            f"  {Colors.question('Enable local host executor (file + command actions)? [y/N]')} "
        ).strip().lower()
        if yn != "y":
            self._update_env_key("NEXA_HOST_EXECUTOR_ENABLED", "false")
            print(
                f"  {Colors.DIM}Left NEXA_HOST_EXECUTOR_ENABLED=false — agents will not run host actions here.{Colors.RESET}"
            )
            return True

        default_root = (self._get_env_value("NEXA_WORKSPACE_ROOT") or "").strip() or str(
            Path.home() / "aethos-workspace"
        )
        path_raw = prompt_line(
            f"  {Colors.question(f'Host / workspace root path [{default_root}]')} "
        ).strip()
        work_path = path_raw or default_root
        p = Path(work_path).expanduser()
        try:
            p.mkdir(parents=True, exist_ok=True)
            resolved = str(p.resolve())
        except OSError as e:
            print(f"  {Colors.error(f'Cannot use path: {e}')}")
            return False

        self._update_env_key("NEXA_HOST_EXECUTOR_ENABLED", "true")
        self._update_env_key("HOST_EXECUTOR_WORK_ROOT", resolved)
        self._update_env_key("NEXA_WORKSPACE_ROOT", resolved)
        print(f"  {Colors.success(f'NEXA_HOST_EXECUTOR_ENABLED=true; HOST_EXECUTOR_WORK_ROOT={resolved}')}")
        print(
            f"  {Colors.warning('Host actions can modify files under this tree — use a dedicated folder.')}"
        )

        reg = prompt_line(
            f"  {Colors.question('Register this path as a Mission Control workspace root when the API is up? [Y/n]')} "
        ).strip().lower()
        if reg in ("", "y", "yes"):
            self.pending_workspace = (resolved, "setup_workspace")
            print(
                f"  {Colors.info('Will POST /api/v1/web/workspace/roots during verification if the API responds.')}"
            )
        return True

    def setup_database(self) -> bool:
        print(f"\n{Colors.step(5, TOTAL_STEPS, 'Initializing database…')}\n")
        print(f"  {Colors.info('Running app.core.db.ensure_schema()')}")
        child_env = {
            **os.environ,
            **self._env_for_subprocess(),
            "PYTHONPATH": str(self.repo_root) + os.pathsep + os.environ.get("PYTHONPATH", ""),
        }
        code = subprocess.run(
            [
                sys.executable,
                "-c",
                "from app.core.db import ensure_schema; ensure_schema()",
            ],
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            timeout=120,
            env=child_env,
        ).returncode
        if code == 0:
            print(f"  {Colors.success('Database schema ready')}")
            return True
        print(f"  {Colors.warning('ensure_schema failed — fix DATABASE_URL and run: aethos init-db')}")
        return False

    def _env_for_subprocess(self) -> dict[str, str]:
        """Load .env into child env for DATABASE_URL etc."""
        out: dict[str, str] = {}
        if not self.env_path.is_file():
            return out
        for line in self.env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip().strip('"').strip("'")
        return out

    def start_services(self) -> bool:
        print(f"\n{Colors.step(8, TOTAL_STEPS, 'Starting API (optional smoke test)…')}\n")
        if self.skip_services:
            print(f"  {Colors.info('Skipped (--skip-services)')}")
            return True
        api_base = self._get_env_value("API_BASE_URL") or "http://127.0.0.1:8010"
        port = parse_port_from_api_base(api_base)
        ok, msg = Validator.check_port(port)
        if not ok:
            print(f"  {Colors.warning(f'Port {port} busy — {msg}')}")
            print(f"  {Colors.dim('Start the API manually after freeing the port.')}")
            return True
        print(f"  {Colors.info(f'Starting uvicorn on {port} (child process)')}")
        log_dir = _REPO_ROOT / ".setup"
        log_dir.mkdir(parents=True, exist_ok=True)
        out_log = open(log_dir / "uvicorn.setup.log", "ab", buffering=0)
        api_env = {
            **os.environ,
            **self._env_for_subprocess(),
            "PYTHONPATH": str(self.repo_root) + os.pathsep + os.environ.get("PYTHONPATH", ""),
        }
        self._api_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
            ],
            cwd=str(self.repo_root),
            stdout=out_log,
            stderr=subprocess.STDOUT,
            env=api_env,
        )
        pid_path = log_dir / "uvicorn.setup.pid"
        pid_path.write_text(str(self._api_process.pid), encoding="utf-8")
        # Brief wait for bind
        import time

        for _ in range(30):
            time.sleep(0.2)
            ok2, _ = Validator.check_port(port)
            if not ok2:
                # port now in use = likely our server
                print(f"  {Colors.success(f'API listening on http://127.0.0.1:{port}')}")
                return True
        print(f"  {Colors.warning('API did not bind in time — see .setup/uvicorn.setup.log')}")
        return True

    def _register_pending_workspace(self, api_base: str, web_user: str, token: str) -> None:
        """POST Mission Control workspace root (requires DB + authenticated API)."""
        if self._workspace_register_done or not self.pending_workspace:
            return
        path, label = self.pending_workspace
        if not token or not web_user:
            print(
                f"  {Colors.warning('Skipping workspace registration (missing token or TEST_X_USER_ID)')}"
            )
            return
        url = f"{api_base.rstrip('/')}/api/v1/web/workspace/roots"
        body = json.dumps({"path": path, "label": label}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("X-User-Id", web_user)
        req.add_header("Authorization", f"Bearer {token}")
        try:
            urllib.request.urlopen(req, timeout=20)
            print(
                f"  {Colors.success('Workspace root registered (POST /api/v1/web/workspace/roots)')}"
            )
            self._workspace_register_done = True
            self.pending_workspace = None
        except urllib.error.HTTPError as e:
            print(
                f"  {Colors.warning(f'Workspace registration HTTP {e.code} — add the root in Mission Control if needed.')}"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  {Colors.warning(f'Workspace registration skipped: {exc!s}')}")

    def verify_installation(self) -> bool:
        print(f"\n{Colors.step(9, TOTAL_STEPS, 'Verifying installation…')}\n")
        api_base = (self._get_env_value("API_BASE_URL") or "http://127.0.0.1:8010").rstrip("/")

        token = (self._get_env_value("NEXA_WEB_API_TOKEN") or "").strip()
        web_user = (
            (self._get_env_value("TEST_X_USER_ID") or "").strip()
            or "web_setup_wizard"
        )

        health_url = f"{api_base}/api/v1/health"
        agents_url = f"{api_base}/api/v1/agents/list"
        reg_url = f"{api_base}/api/v1/marketplace/-/registry-status"

        checks: list[tuple[str, str, bool]] = [
            ("Health (no auth)", health_url, False),
            ("Agents list (auth)", agents_url, True),
            ("Marketplace registry (auth)", reg_url, True),
        ]

        all_passed = True

        def _req(url: str, *, needs_auth: bool) -> tuple[bool, str]:
            try:
                r = urllib.request.Request(url)
                if needs_auth:
                    r.add_header("X-User-Id", web_user)
                    if token:
                        r.add_header("Authorization", f"Bearer {token}")
                with urllib.request.urlopen(r, timeout=10) as resp:
                    return resp.status == 200, f"HTTP {resp.status}"
            except urllib.error.HTTPError as e:
                return False, f"HTTP {e.code}"
            except Exception as exc:  # noqa: BLE001
                return False, str(exc)[:120]

        for name, url, needs_auth in checks:
            if needs_auth and not token:
                print(f"  {Colors.warning(f'{name} — skipped (NEXA_WEB_API_TOKEN missing)')}")
                all_passed = False
                continue
            ok, detail = _req(url, needs_auth=needs_auth)
            if ok and name.startswith("Health"):
                self._register_pending_workspace(api_base, web_user, token)
            if ok:
                print(f"  {Colors.success(f'{name} — {detail}')}")
                continue
            print(f"  {Colors.error(f'{name} — {detail}')}")
            if needs_auth and "401" in detail:
                print(
                    f"  {Colors.DIM}Check TEST_X_USER_ID, NEXA_WEB_API_TOKEN, and restart the API to load .env.{Colors.RESET}"
                )
            all_passed = False

        return all_passed

    def _update_env_key(self, key: str, value: str) -> None:
        lines: list[str] = []
        if self.env_path.is_file():
            lines = self.env_path.read_text(encoding="utf-8").splitlines()
        updated = False
        prefix = f"{key}="
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in line:
                continue
            k, _, _ = line.partition("=")
            if k.strip() == key:
                lines[i] = f"{key}={value}"
                updated = True
                break
        if not updated:
            lines.append(f"{key}={value}")
        self.env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _get_env_value(self, key: str) -> str | None:
        if not self.env_path.is_file():
            return None
        for line in self.env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == key:
                return v.strip().strip('"').strip("'")
        return None

    # --- flow ---

    def prompt_overwrite(self) -> bool:
        print(f"\n{Colors.warning('Existing configuration detected (.env present).')}")
        print(f"  {Colors.DIM}A backup will be written before changes.{Colors.RESET}")
        out = prompt_line(f"\n{Colors.question('Re-run full setup (override)? [y/N]')} ").strip().lower()
        return out == "y"

    def run(self) -> None:
        self.print_banner()
        display_legal_notice(force=self.force, accept_disclaimer=self.accept_disclaimer)
        if self.full_reset and STATE_FILE.exists():
            STATE_FILE.unlink()
        state = self._load_state()
        completed = set(state.get("completed_steps") or [])

        if self.env_path.is_file() and not self.full_reset:
            if self.force:
                print(f"\n{Colors.info('Force mode — proceeding (existing .env will be backed up).')}")
            elif not self.prompt_overwrite():
                print(f"\n{Colors.info('Keeping existing .env — exiting.')}")
                return

        if self.resume and completed and not self.full_reset:
            print(f"{Colors.info(f'Previous progress: {sorted(completed)}')}")

        print(f"\n{Colors.BOLD}{Colors.GREEN}Let's configure AethOS{Colors.RESET}")
        print(f"{Colors.DIM}Roughly 2–5 minutes depending on pip.{Colors.RESET}")
        prompt_line(f"\n{Colors.question('Press Enter to begin…')} ")

        steps: list[tuple[str, str, Callable[[], bool]]] = [
            ("requirements", "Check system requirements", self.check_requirements),
            ("dependencies", "Install dependencies", self.install_dependencies),
            ("environment", "Configure .env", self.configure_env),
            ("authentication", "Authentication (user id + token)", self.configure_authentication),
            ("database", "Initialize database", self.setup_database),
            ("llm_keys", "LLM keys (optional)", self.configure_llm_keys),
            ("host_executor", "Host executor (local runs)", self.configure_host_executor),
            ("services", "Start API (optional)", self.start_services),
            ("verify", "Verify HTTP endpoints", self.verify_installation),
        ]

        for i, (sid, label, fn) in enumerate(steps, start=1):
            if self.resume and sid in completed and not self.full_reset:
                print(f"\n{Colors.step(i, TOTAL_STEPS, f'Skipping (already completed): {label}')}")
                self.results[sid] = True
                continue
            print(f"\n{Colors.step(i, TOTAL_STEPS, label)}")
            ok = fn()
            self.results[sid] = ok
            self._save_state()
            if not ok:
                print(f"\n{Colors.warning('Step did not fully succeed.')}")
                cont = prompt_line(f"{Colors.question('Continue to next step? [Y/n]')} ").strip().lower()
                if cont == "n":
                    print(f"\n{Colors.error('Stopped. Fix issues and re-run, or use --resume.')}")
                    return

        print(Colors.header("Setup complete"))
        api_base = self._get_env_value("API_BASE_URL") or "http://127.0.0.1:8010"
        port = parse_port_from_api_base(api_base)
        connect_uid = (self._get_env_value("TEST_X_USER_ID") or "").strip() or "your-user-id"
        full_tok = (self._get_env_value("NEXA_WEB_API_TOKEN") or "").strip()
        if len(full_tok) > 42:
            tok_show = f"{full_tok[:30]}…{full_tok[-10:]}"
        else:
            tok_show = full_tok or "(set NEXA_WEB_API_TOKEN)"

        print(
            f"""
{Colors.GREEN}AethOS is configured.{Colors.RESET}

{Colors.BOLD}Connection details (Mission Control){Colors.RESET}
{Colors.CYAN}{'─' * 52}{Colors.RESET}
  API base:     {Colors.BOLD}{api_base}{Colors.RESET}
  X-User-Id:    {Colors.BOLD}{connect_uid}{Colors.RESET}
  Bearer token: {Colors.BOLD}{tok_show}{Colors.RESET}
{Colors.CYAN}{'─' * 52}{Colors.RESET}

{Colors.BOLD}Next steps:{Colors.RESET}

1. {Colors.CYAN}Web UI{Colors.RESET}: {Colors.DIM}cd web && npm install && npm run dev{Colors.RESET} → usually {Colors.DIM}http://localhost:3000{Colors.RESET}

2. {Colors.CYAN}In the app{Colors.RESET}, open connection / settings and set:
   • API base URL → {Colors.BOLD}{api_base}{Colors.RESET}
   • Bearer token → {Colors.BOLD}(full value from .env: NEXA_WEB_API_TOKEN){Colors.RESET}
   • X-User-Id → {Colors.BOLD}{connect_uid}{Colors.RESET}

3. {Colors.CYAN}API{Colors.RESET} (if not running):  
   {Colors.DIM}cd {_REPO_ROOT} && source .venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --reload --port {port}{Colors.RESET}

4. {Colors.CYAN}Credentials file{Colors.RESET}: {Colors.DIM}{CREDS_FILE_HOME}{Colors.RESET}

5. {Colors.DIM}Quick view:{Colors.RESET} {Colors.DIM}./scripts/show_credentials.sh{Colors.RESET}

{Colors.DIM}Also see ``.env.example`` and repo ``docs/``.{Colors.RESET}
"""
        )


def main() -> None:
    argv = sys.argv[1:]
    if _parse_help_argv(argv):
        return

    parser = argparse.ArgumentParser(
        description="AethOS interactive setup wizard",
        add_help=False,
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip steps recorded as completed in .aethos_setup_state.json",
    )
    parser.add_argument(
        "--skip-services",
        action="store_true",
        help="Do not spawn uvicorn for smoke test",
    )
    parser.add_argument(
        "--full-reset",
        action="store_true",
        help="Ignore saved progress and run every step",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip overwrite confirmation when .env exists (non-interactive)",
    )
    parser.add_argument(
        "--accept-disclaimer",
        action="store_true",
        help="Acknowledge LICENSE.disclaimer without interactive prompt (for automation)",
    )
    args, _rest = parser.parse_known_args(argv)

    # Allow ``python scripts/setup.py help llm`` after argparse
    if _rest and _parse_help_argv(_rest):
        return

    wizard = SetupWizard(
        resume=args.resume,
        skip_services=args.skip_services,
        full_reset=args.full_reset,
        force=args.force,
        accept_disclaimer=args.accept_disclaimer,
    )
    try:
        wizard.run()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.warning('Setup cancelled')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
