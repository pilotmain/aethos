#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""AethOS interactive setup wizard — first-run and re-run with backup + validation."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
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

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from app.core.web_api_token import generate_web_api_token  # noqa: E402


STATE_FILE = _REPO_ROOT / ".aethos_setup_state.json"
BACKUP_SUBDIR = _REPO_ROOT / ".setup" / "backups"
TOTAL_STEPS = 9
CREDS_FILE_HOME = Path.home() / ".aethos_credentials"


def get_canonical_user_id(telegram_id: str | None = None) -> str:
    """
    Default Mission Control X-User-Id for setup when the operator presses Enter.

    If a Telegram-style id is provided (``tg_<digits>``), use it as the canonical id.
    Otherwise generate a stable random ``web_<hex>`` id (not timestamp-based).
    """
    t = (telegram_id or "").strip()
    if t.startswith("tg_"):
        return t
    return f"web_{uuid.uuid4().hex[:16]}"


def _legal_auto_accept_noninteractive() -> bool:
    """True for piped stdin (e.g. curl | bash), Docker, or CI runners — no extra env vars needed."""
    if not sys.stdin.isatty():
        return True
    if (os.environ.get("CI") or "").strip():
        return True
    if (os.environ.get("GITHUB_ACTIONS") or "").strip():
        return True
    return False


def reattach_tty_stdin_if_needed() -> None:
    """After legal auto-accept, read prompts from /dev/tty when stdin was a pipe (curl | bash)."""
    if (os.environ.get("CI") or "").strip() or (os.environ.get("GITHUB_ACTIONS") or "").strip():
        return
    if (os.environ.get("NEXA_NONINTERACTIVE") or "").strip().lower() in ("1", "true", "yes"):
        return
    if sys.stdin.isatty():
        return
    try:
        sys.stdin = open("/dev/tty", "r", encoding="utf-8", errors="replace")  # noqa: SIM115
    except OSError:
        pass


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

    if _legal_auto_accept_noninteractive():
        print(
            f"{Colors.DIM}Non-interactive / CI: continuing as if you accepted the terms above "
            f"(see LICENSE.disclaimer). For an explicit prompt, run this wizard in a TTY.{Colors.RESET}\n"
        )
        return

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
        try:
            raw = input(prompt)
        except EOFError:
            return ""
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


def resolve_setup_env_path(repo_root: Path, *, use_home_env_flag: bool = False) -> Path:
    """Where the wizard writes ``.env``: repo root for a fresh clone; ``~/.aethos/.env`` for one-curl / home install.

    Override: ``AETHOS_SETUP_REPO_ENV=1`` → always ``<repo>/.env``.
    Prefer home when: ``--home-env``, ``AETHOS_ONE_CURL=1``, or ``~/.aethos/.env`` already exists.
    """
    repo_env = repo_root / ".env"
    home_root = Path.home() / ".aethos"
    home_env = home_root / ".env"
    force_repo = (os.environ.get("AETHOS_SETUP_REPO_ENV") or "").strip().lower() in ("1", "true", "yes")
    if force_repo:
        return repo_env
    one_curl = (os.environ.get("AETHOS_ONE_CURL") or "").strip().lower() in ("1", "true", "yes")
    if use_home_env_flag or one_curl or home_env.is_file():
        home_root.mkdir(parents=True, exist_ok=True)
        return home_env
    return repo_env


def dedupe_env_assignment_lines(path: Path) -> None:
    """Remove duplicate active ``KEY=value`` lines (last assignment wins). Preserves comments and blanks."""
    if not path.is_file():
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    last_val: dict[str, str] = {}
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k:
            last_val[k] = v
    out: list[str] = []
    seen: set[str] = set()
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in line:
            out.append(line)
            continue
        k, _, _ = line.partition("=")
        k = k.strip()
        if not k or k not in last_val:
            out.append(line)
            continue
        if k in seen:
            continue
        out.append(f"{k}={last_val[k]}")
        seen.add(k)
    for k, v in last_val.items():
        if k not in seen:
            out.append(f"{k}={v}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def ollama_cli_on_path() -> bool:
    """True when the ``ollama`` executable is on PATH (does not verify ``ollama serve`` or pulled models)."""
    return shutil.which("ollama") is not None


def _aethos_auto_register_workspace_default() -> bool:
    """When true (default), queue workspace API registration without an extra prompt."""
    v = (os.environ.get("AETHOS_AUTO_REGISTER_WORKSPACE") or "true").strip().lower()
    return v in ("1", "true", "yes", "y", "")


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
        no_browser: bool = False,
        skip_playwright_browsers: bool = False,
        use_home_env: bool = False,
    ) -> None:
        self.repo_root = _REPO_ROOT
        self.env_path = resolve_setup_env_path(self.repo_root, use_home_env_flag=use_home_env)
        self.env_example = self.repo_root / ".env.example"
        self.requirements = self.repo_root / "requirements.txt"
        self.pyproject = self.repo_root / "pyproject.toml"
        self.resume = resume
        self.skip_services = skip_services
        self.full_reset = full_reset
        self.accept_disclaimer = accept_disclaimer
        self.no_browser = bool(no_browser)
        self.skip_playwright_browsers = bool(skip_playwright_browsers)
        self._setup_playwright_browsers_enabled: bool = False
        env_force = (os.environ.get("AETHOS_SETUP_FORCE") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        )
        self.force = bool(force or env_force)
        self.results: dict[str, bool] = {}
        self._api_process: subprocess.Popen[bytes] | None = None
        self._web_process: subprocess.Popen[bytes] | None = None
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
            f"{Colors.DIM}Environment file target: {Colors.CYAN}{self.env_path.resolve()}{Colors.DIM} "
            f"(use AETHOS_SETUP_REPO_ENV=1 to force repo-root .env){Colors.RESET}"
        )
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
        self._optional_install_vercel_cli()
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
        try:
            from app.services.deployment.cloud_config import init_cloud_config_file

            cpath = init_cloud_config_file()
            print(f"  {Colors.info(f'Deploy providers config: {cpath}')}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {Colors.warning(f'Optional clouds.yaml init skipped: {exc}')}")
        return True

    def _optional_install_vercel_cli(self) -> None:
        """Best-effort Vercel CLI for local deploy flows (``vercel`` / ``vercel whoami``)."""
        if not shutil.which("npm"):
            return
        if shutil.which("vercel"):
            return
        if _legal_auto_accept_noninteractive():
            print(f"  {Colors.info('Installing Vercel CLI globally (non-interactive setup)…')}")
            r = subprocess.run(
                ["npm", "install", "-g", "vercel"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=600,
            )
            if r.returncode == 0:
                print(f"  {Colors.success('Vercel CLI installed')}")
            else:
                tail = (r.stderr or r.stdout or "")[-300:]
                print(f"  {Colors.warning(f'Vercel CLI install skipped: {tail}')}")
            return
        yn = prompt_line(
            f"  {Colors.question('Install Vercel CLI globally for deployments? [y/N]')} "
        ).strip().lower()
        if yn not in ("y", "yes"):
            print(f"  {Colors.DIM}Skip — run: npm install -g vercel{Colors.RESET}")
            return
        print(f"  {Colors.info('npm install -g vercel …')}")
        r = subprocess.run(
            ["npm", "install", "-g", "vercel"],
            cwd=str(self.repo_root),
            capture_output=True,
            text=True,
            timeout=600,
        )
        if r.returncode == 0:
            print(f"  {Colors.success('Vercel CLI installed')}")
        else:
            tail = (r.stderr or r.stdout or "")[-300:]
            print(f"  {Colors.warning(f'Vercel CLI install failed: {tail}')}")

    def _setup_wants_playwright_browser(self) -> bool:
        """Whether to install Chromium and write browser defaults into ``.env``."""
        if self.skip_playwright_browsers:
            return False
        if (os.environ.get("AETHOS_SETUP_SKIP_PLAYWRIGHT_BROWSERS") or "").strip().lower() in (
            "1",
            "true",
            "yes",
        ):
            return False
        if _legal_auto_accept_noninteractive():
            return True
        yn = prompt_line(
            f"  {Colors.question('Enable browser automation (Playwright / Chromium)? [Y/n]')} "
        ).strip().lower()
        return yn not in ("n", "no")

    def _install_playwright_browsers(self) -> bool:
        """Download Chromium for Playwright (``python -m playwright install chromium``)."""
        print(f"\n  {Colors.info('Installing Playwright browsers (Chromium)…')}")
        try:
            r = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=900,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"  {Colors.warning(f'Playwright browser install failed: {exc!s}')}")
            return False
        if r.returncode != 0:
            tail = ((r.stderr or "") + (r.stdout or ""))[-600:].strip()
            print(f"  {Colors.warning('Playwright ``install chromium`` exited non-zero')}")
            if tail:
                print(f"  {Colors.DIM}{tail}{Colors.RESET}")
            return False
        print(f"  {Colors.success('Playwright Chromium installed')}")
        return True

    def _upsert_env_if_unset(self, key: str, value: str) -> bool:
        """Set ``key=value`` only when the key is missing or blank in ``.env``."""
        cur = self._get_env_value(key)
        if cur is not None and str(cur).strip():
            return False
        self._update_env_key(key, value)
        return True

    def _apply_setup_default_env_overlay(self) -> None:
        """Fill standard keys from the setup template when missing or blank (no duplicate active lines)."""
        ws = (self._get_env_value("NEXA_WORKSPACE_ROOT") or "").strip() or str(Path.home() / "aethos-workspace")
        home_s = str(Path.home())
        pairs: list[tuple[str, str]] = [
            ("APP_NAME", "AethOS"),
            ("APP_ENV", "development"),
            ("DEBUG", "true"),
            ("USE_REAL_LLM", "true"),
            ("NEXA_AGENT_ORCHESTRATION_ENABLED", "true"),
            ("NEXA_AUTONOMOUS_GOAL_PLANNING", "true"),
            ("NEXA_SELF_HEALING_ENABLED", "true"),
            ("NEXA_SELF_IMPROVEMENT_ENABLED", "true"),
            ("NEXA_COMMAND_TIMEOUT_SECONDS", "300"),
            ("NEXA_TASK_TIMEOUT_SECONDS", "300"),
            ("NEXA_COMMAND_EXECUTION_ENABLED", "true"),
            ("NEXA_HOST_EXECUTOR_ENABLED", "true"),
            ("NEXA_COMMAND_WORK_ROOT", ws),
            ("HOST_EXECUTOR_WORK_ROOT", home_s),
            ("NEXA_WORKSPACE_ROOT", ws),
            ("NEXA_BROWSER_ENABLED", "true"),
            ("NEXA_BROWSER_HEADLESS", "false"),
            ("NEXA_BROWSER_ALLOWED_DOMAINS", "*"),
            ("NEXA_TELEGRAM_EMBED_WITH_API", "true"),
            ("NEXA_GENERIC_DEPLOY_ENABLED", "true"),
            ("NEXA_DEPLOY_AUTO_DETECT", "true"),
            ("NEXA_DEPLOY_TIMEOUT_SECONDS", "300"),
            ("NEXA_OBSERVABILITY_ENABLED", "true"),
            ("NEXA_RESPONSE_FORMAT", "beautiful"),
            ("NEXA_AUTO_APPROVE_OWNER", "true"),
            ("AETHOS_OWNER_IDS", ""),
            ("TELEGRAM_OWNER_IDS", ""),
            ("NEXA_SELF_IMPROVEMENT_OWNER_ID", ""),
            ("ANTHROPIC_API_KEY", ""),
            ("OPENAI_API_KEY", ""),
        ]
        for k, v in pairs:
            self._upsert_env_if_unset(k, v)
        # Prefer real LLM for agents / custom agents; operators may set false explicitly in .env.
        low_llm = (self._get_env_value("USE_REAL_LLM") or "").strip().lower()
        if low_llm in ("false", "0", "no", ""):
            self._update_env_key("USE_REAL_LLM", "true")

    def _apply_ollama_autodetect_to_env(self) -> None:
        """If ``ollama`` is on PATH, prefer local HTTP backend (matches ``providers_available()`` / bootstrap)."""
        if not self.env_path.is_file():
            return
        if ollama_cli_on_path():
            self._update_env_key("NEXA_OLLAMA_ENABLED", "true")
            self._update_env_key("NEXA_LLM_PROVIDER", "ollama")
            self._upsert_env_if_unset("NEXA_OLLAMA_DEFAULT_MODEL", "qwen2.5:7b")
            self._update_env_key("NEXA_PURE_LOCAL_LLM_MODE", "true")
            print(
                f"  {Colors.success('Ollama CLI on PATH — local LLM is primary (Ollama enabled, pure local LLM mode on).')}"
            )
            print(
                f"  {Colors.DIM}Start or keep `ollama serve` running and pull a model (default tag when unset: "
                f"qwen2.5:7b). Optional cloud keys in the next wizard step are fallbacks only.{Colors.RESET}"
            )
        else:
            print(
                f"  {Colors.DIM}Ollama CLI not on PATH — left NEXA_OLLAMA_ENABLED / provider as in template "
                f"(install from https://ollama.com for local models).{Colors.RESET}"
            )

    def _print_llm_configuration_summary(self) -> None:
        """Summarize primary vs optional cloud fallbacks after .env is written."""
        if not self.env_path.is_file():
            return

        def _truthy(val: str | None) -> bool:
            return (val or "").strip().lower() in ("1", "true", "yes", "on")

        line_sep = "=" * 50
        print(f"\n{line_sep}")
        print(f"  {Colors.BOLD}LLM configuration summary{Colors.RESET}")
        ollama_primary = _truthy(self._get_env_value("NEXA_OLLAMA_ENABLED")) and (
            (self._get_env_value("NEXA_LLM_PROVIDER") or "").strip().lower() == "ollama"
        )
        model = (self._get_env_value("NEXA_OLLAMA_DEFAULT_MODEL") or "qwen2.5:7b").strip()
        if ollama_primary:
            print(f"  {Colors.success('Primary:')} Ollama (local) — default model tag: {model}")
        elif ollama_cli_on_path():
            print(
                f"  {Colors.warning('Ollama CLI on PATH but .env does not show Ollama as primary — check NEXA_OLLAMA_ENABLED / NEXA_LLM_PROVIDER.')}"
            )
        if _truthy(self._get_env_value("NEXA_PURE_LOCAL_LLM_MODE")):
            print(
                f"  {Colors.info('Pure local LLM mode: ON (Ollama-first intent/chat when a provider is up)')}"
            )

        def _looks_configured(key: str, prefix: str | None) -> bool:
            raw = (self._get_env_value(key) or "").strip()
            if not raw or raw.startswith("#") or len(raw) <= 8:
                return False
            if prefix is not None and not raw.startswith(prefix):
                return False
            return True

        if _looks_configured("ANTHROPIC_API_KEY", "sk-ant-"):
            print(f"  {Colors.success('Fallback:')} Anthropic Claude")
        if _looks_configured("OPENAI_API_KEY", "sk-"):
            print(f"  {Colors.success('Fallback:')} OpenAI")
        if _looks_configured("DEEPSEEK_API_KEY", None):
            print(f"  {Colors.success('Fallback:')} DeepSeek")

        has_cloud = any(
            _looks_configured(k, p)
            for k, p in (
                ("ANTHROPIC_API_KEY", "sk-ant-"),
                ("OPENAI_API_KEY", "sk-"),
                ("DEEPSEEK_API_KEY", None),
            )
        )
        if not ollama_primary and not has_cloud:
            print(
                f"  {Colors.warning('No LLM providers in .env — heuristics / templates only until Ollama or a cloud key is configured.')}"
            )
        elif ollama_primary and not has_cloud:
            print(
                f"  {Colors.DIM}No cloud keys — fine for fully local runs; add one if you want a paid fallback.{Colors.RESET}"
            )
        print(line_sep)

    def _sync_self_improvement_and_owners_for_user(self, user_id: str) -> None:
        """Always enable self-improvement; bind owner gates to the Mission Control web user id."""
        self._update_env_key("NEXA_SELF_IMPROVEMENT_ENABLED", "true")
        self._update_env_key("AETHOS_OWNER_IDS", user_id)
        if not (self._get_env_value("NEXA_SELF_IMPROVEMENT_OWNER_ID") or "").strip():
            self._update_env_key("NEXA_SELF_IMPROVEMENT_OWNER_ID", user_id)
        if user_id.startswith("tg_") and user_id[3:].isdigit():
            self._merge_telegram_owner_ids(user_id[3:])

    def _ensure_playwright_env_defaults(self, *, browser_enabled: bool) -> None:
        """Append browser / host defaults to ``.env`` when keys are unset."""
        if not self.env_path.is_file():
            return
        if not browser_enabled:
            if self._upsert_env_if_unset("NEXA_BROWSER_ENABLED", "false"):
                print(f"  {Colors.info('Set NEXA_BROWSER_ENABLED=false (browser automation declined)')}")
            self._upsert_env_if_unset("NEXA_BROWSER_AUTOMATION_ENABLED", "false")
            return

        banner = "# Browser automation (Playwright) — setup wizard"
        raw = self.env_path.read_text(encoding="utf-8")
        if banner not in raw:
            self.env_path.write_text(raw.rstrip() + f"\n\n{banner}\n", encoding="utf-8")

        default_root = (self._get_env_value("NEXA_WORKSPACE_ROOT") or "").strip() or str(
            Path.home() / "aethos-workspace"
        )
        added: list[str] = []
        pairs: list[tuple[str, str]] = [
            ("NEXA_HOST_EXECUTOR_ENABLED", "true"),
            ("NEXA_BROWSER_AUTOMATION_ENABLED", "true"),
            ("NEXA_BROWSER_ENABLED", "true"),
            ("NEXA_BROWSER_HEADLESS", "false"),
            ("NEXA_BROWSER_ALLOWED_DOMAINS", "*"),
            ("NEXA_BROWSER_TIMEOUT_SECONDS", "30"),
        ]
        for k, v in pairs:
            if self._upsert_env_if_unset(k, v):
                added.append(k)
        if self._upsert_env_if_unset("HOST_EXECUTOR_WORK_ROOT", default_root):
            added.append("HOST_EXECUTOR_WORK_ROOT")
        if added:
            print(
                f"  {Colors.success('Added browser / host executor defaults to .env: ' + ', '.join(added))}"
            )

    def _configure_playwright_after_env(self) -> None:
        """Prompt, write ``.env`` keys, and install Chromium after core ``.env`` fields exist."""
        wants = self._setup_wants_playwright_browser()
        self._setup_playwright_browsers_enabled = wants
        self._ensure_playwright_env_defaults(browser_enabled=wants)
        if wants:
            self._install_playwright_browsers()
        else:
            print(
                f"  {Colors.DIM}Skipped Playwright browser download (enable later: re-run setup or "
                f"`{sys.executable} -m playwright install chromium`).{Colors.RESET}"
            )

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
            wt = generate_web_api_token()
            self._update_env_key("NEXA_WEB_API_TOKEN", wt)
            print(f"  {Colors.success('Generated NEXA_WEB_API_TOKEN (for Mission Control auth)')}")

        wr = self._get_env_value("NEXA_WORKSPACE_ROOT")
        if not wr:
            default_wr = str(Path.home() / "aethos-workspace")
            self._update_env_key("NEXA_WORKSPACE_ROOT", default_wr)
            print(f"  {Colors.info(f'Default workspace root → {default_wr}')}")

        self._configure_playwright_after_env()
        self._apply_setup_default_env_overlay()
        self._apply_ollama_autodetect_to_env()
        # One-curl / wizard installs: OpenClaw-style gateway (tools/NL first, then trust the LLM for chat).
        self._update_env_key("NEXA_LLM_FIRST_GATEWAY", "true")
        self._update_env_key("USE_REAL_LLM", "true")
        print(
            f"  {Colors.success('NEXA_LLM_FIRST_GATEWAY=true; USE_REAL_LLM=true (restart API to load if already running)')}"
        )
        dedupe_env_assignment_lines(self.env_path)
        print(
            f"\n  {Colors.success('Environment file (deduplicated keys):')} "
            f"{Colors.CYAN}{self.env_path.resolve()}{Colors.RESET}"
        )
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

    def _print_aethos_ready_banner(self, *, api_base_url: str, user_id: str, token: str) -> None:
        """Prominent summary after auth is written to ``.env`` (Mission Control auto-loads these values)."""
        ab = (api_base_url or "http://127.0.0.1:8010").strip().rstrip("/")
        tok = (token or "").strip()
        if len(tok) > 30:
            tok_show = f"{tok[:20]}...{tok[-10:]}"
        elif tok:
            tok_show = tok
        else:
            tok_show = "(set NEXA_WEB_API_TOKEN)"
        bar = "=" * 60
        print(f"\n{bar}")
        print(f"{Colors.GREEN}✅ AETHOS IS READY{Colors.RESET}")
        print(bar)
        print(f"{Colors.CYAN}🌐 Mission Control:{Colors.RESET} http://localhost:3000")
        print(f"{Colors.CYAN}📡 API:{Colors.RESET} {ab}")
        print(f"{Colors.CYAN}🔑 API docs:{Colors.RESET} {ab}/docs")
        print("")
        print(f"{Colors.BOLD}🔐 Your login credentials (already filled in the browser when Mission Control runs):{Colors.RESET}")
        print(f"   • API Base URL: {ab}")
        print(f"   • X-User-Id: {user_id}")
        print(f"   • Bearer Token: {tok_show}")
        print("")
        print(f"{Colors.DIM}🚀 The browser opens after services start. If not, go to http://localhost:3000{Colors.RESET}")
        print(f"{bar}\n")

    def configure_authentication(self) -> bool:
        """Collect Mission Control user id, optional Telegram token, display bearer token."""
        print(f"\n{Colors.step(4, TOTAL_STEPS, 'Authentication (web API)…')}\n")
        print(
            f"  {Colors.info('Mission Control requests X-User-Id + Bearer token when NEXA_WEB_API_TOKEN is set.')}"
        )
        print(
            f"  {Colors.DIM}Enter your Telegram user id as tg_<digits> if you use Telegram, or press Enter for a "
            f"stable random web id.{Colors.RESET}"
        )

        default_uid = get_canonical_user_id(None)
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
        self._update_env_key("X_USER_ID", user_id)
        print(f"  {Colors.success(f'Saved TEST_X_USER_ID and X_USER_ID={user_id}')}")
        self._sync_self_improvement_and_owners_for_user(user_id)

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
            web_token = generate_web_api_token()
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

        self._configure_enterprise_sso_and_audit()
        dedupe_env_assignment_lines(self.env_path)
        api_b = (self._get_env_value("API_BASE_URL") or "").strip()
        wtok = (self._get_env_value("NEXA_WEB_API_TOKEN") or "").strip()
        print(f"\n  {Colors.success('Authentication saved to:')} {Colors.CYAN}{self.env_path.resolve()}{Colors.RESET}")
        if api_b:
            print(f"  {Colors.info(f'API_BASE_URL={api_b}')}")
        if wtok:
            preview = f"{wtok[:24]}…{wtok[-8:]}" if len(wtok) > 42 else wtok
            print(f"  {Colors.info(f'NEXA_WEB_API_TOKEN={preview}')}")
        print(f"  {Colors.info(f'TEST_X_USER_ID={user_id}')}")
        self._print_aethos_ready_banner(api_base_url=api_b, user_id=user_id, token=wtok)
        return True

    def _configure_enterprise_sso_and_audit(self) -> None:
        """Write JSONL audit defaults and optional OIDC SSO keys to ``.env`` (no manual editing)."""
        api_base = (
            (self._get_env_value("API_BASE_URL") or self._get_env_value("api_base_url") or "http://127.0.0.1:8010")
            .strip()
            .rstrip("/")
        )
        default_post = "http://localhost:3000/login"
        audit_home = str(Path.home() / ".aethos" / "audit")
        self._update_env_key("AUDIT_ENABLED", "true")
        self._update_env_key("AUDIT_DIR", audit_home)
        self._update_env_key("AUDIT_RETENTION_DAYS", "90")
        print(f"  {Colors.success(f'Enterprise audit log: AUDIT_DIR={audit_home}')}")

        noni = _legal_auto_accept_noninteractive() or (
            (os.environ.get("NEXA_NONINTERACTIVE") or "").strip().lower() in ("1", "true", "yes")
        )
        callback = f"{api_base}/api/v1/sso/callback"
        if noni:
            self._update_env_key("SSO_ENABLED", "false")
            self._update_env_key("SSO_OIDC_ISSUER", "")
            self._update_env_key("SSO_CLIENT_ID", "")
            self._update_env_key("SSO_CLIENT_SECRET", "")
            self._update_env_key("SSO_REDIRECT_URI", callback)
            self._update_env_key("SSO_POST_LOGIN_REDIRECT", default_post)
            return

        yn = prompt_line(
            f"  {Colors.question('Enable Single Sign-On (SSO) via OIDC? [y/N]')} "
        ).strip().lower()
        if yn == "y":
            iss = prompt_line(
                f"  {Colors.question('OIDC issuer URL (e.g. https://accounts.google.com)')} "
            ).strip()
            cid = prompt_line(f"  {Colors.question('OIDC client ID')} ").strip()
            csec = prompt_line(f"  {Colors.question('OIDC client secret')} ").strip()
            post = prompt_line(
                f"  {Colors.question(f'After login, redirect browser to [{default_post}]')} "
            ).strip() or default_post
            if not iss or not cid or not csec:
                print(f"  {Colors.warning('Incomplete SSO answers — leaving SSO_ENABLED=false.')}")
                self._update_env_key("SSO_ENABLED", "false")
                self._update_env_key("SSO_OIDC_ISSUER", iss)
                self._update_env_key("SSO_CLIENT_ID", cid)
                self._update_env_key("SSO_CLIENT_SECRET", csec)
            else:
                self._update_env_key("SSO_ENABLED", "true")
                self._update_env_key("SSO_OIDC_ISSUER", iss.rstrip("/"))
                self._update_env_key("SSO_CLIENT_ID", cid)
                self._update_env_key("SSO_CLIENT_SECRET", csec)
                print(f"  {Colors.success('SSO (OIDC) enabled — values saved to .env')}")
            self._update_env_key("SSO_REDIRECT_URI", callback)
            self._update_env_key("SSO_POST_LOGIN_REDIRECT", (post or default_post).strip())
        else:
            self._update_env_key("SSO_ENABLED", "false")
            self._update_env_key("SSO_OIDC_ISSUER", "")
            self._update_env_key("SSO_CLIENT_ID", "")
            self._update_env_key("SSO_CLIENT_SECRET", "")
            self._update_env_key("SSO_REDIRECT_URI", callback)
            self._update_env_key("SSO_POST_LOGIN_REDIRECT", default_post)
            print(f"  {Colors.DIM}SSO left disabled — set SSO_ENABLED=true when ready.{Colors.RESET}")

    def _minimal_env_blob(self) -> str:
        return f"""# AethOS — generated by scripts/setup.py
APP_NAME=AethOS
APP_ENV=development
API_BASE_URL=http://127.0.0.1:8010
DATABASE_URL={default_sqlite_database_url()}
NEXA_SECRET_KEY={secrets.token_urlsafe(32)}
NEXA_WEB_API_TOKEN={generate_web_api_token()}
NEXA_AGENT_ORCHESTRATION_ENABLED=true
USE_REAL_LLM=true
NEXA_WORKSPACE_ROOT={Path.home() / "aethos-workspace"}
HOST_EXECUTOR_WORK_ROOT={Path.home() / "aethos-workspace"}
# Enterprise — JSONL audit (per day under AUDIT_DIR); set AUDIT_ENABLED=false to disable.
AUDIT_ENABLED=true
AUDIT_DIR={Path.home() / ".aethos" / "audit"}
AUDIT_RETENTION_DAYS=90
# Enterprise — optional OIDC SSO (Google / Okta / Entra). Callback must match IdP app settings.
SSO_ENABLED=false
SSO_OIDC_ISSUER=
SSO_CLIENT_ID=
SSO_CLIENT_SECRET=
SSO_REDIRECT_URI=http://127.0.0.1:8010/api/v1/sso/callback
SSO_POST_LOGIN_REDIRECT=http://localhost:3000/login
# TELEGRAM_BOT_TOKEN=
"""

    def configure_llm_keys(self) -> bool:
        print(f"\n{Colors.step(6, TOTAL_STEPS, 'LLM providers (optional cloud fallbacks)…')}\n")

        def _truthy(val: str | None) -> bool:
            return (val or "").strip().lower() in ("1", "true", "yes", "on")

        ollama_primary = _truthy(self._get_env_value("NEXA_OLLAMA_ENABLED")) and (
            (self._get_env_value("NEXA_LLM_PROVIDER") or "").strip().lower() == "ollama"
        )
        if ollama_primary:
            print(
                f"  {Colors.info('Ollama is the primary LLM. Cloud keys below are optional fallbacks if Ollama is down.')}"
            )
        elif ollama_cli_on_path():
            print(
                f"  {Colors.warning('Ollama is on PATH; if .env does not show Ollama as primary, re-run the environment step or edit .env.')}"
            )
        else:
            print(
                f"  {Colors.info('Install https://ollama.com and re-run setup to prefer local models first; keys below are optional paid fallbacks.')}"
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
            yn = prompt_line(
                f"  {Colors.question(f'Add {name} API key as optional fallback? [y/N]')} "
            ).strip().lower()
            if yn != "y":
                continue
            key = prompt_line(f"  {Colors.question(f'{name} API key')} ").strip()
            if not key:
                print(f"  {Colors.warning('Skipped empty key')}")
                continue
            if prefix and not key.startswith(prefix):
                print(
                    f"  {Colors.warning(f'Invalid key format for {name} (expected prefix {prefix!r}) — skipping.')}"
                )
                continue
            self._update_env_key(env_key, key)
            print(f"  {Colors.success(f'{name} saved to .env (fallback when configured)')}")
            configured += 1
        if configured == 0:
            print(f"\n  {Colors.warning('No new cloud LLM keys added — you can edit .env later.')}")
        self._print_llm_configuration_summary()
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
        he_cur = (self._get_env_value("NEXA_HOST_EXECUTOR_ENABLED") or "").strip().lower()
        wr_cur = (self._get_env_value("HOST_EXECUTOR_WORK_ROOT") or "").strip()
        if (
            getattr(self, "_setup_playwright_browsers_enabled", False)
            and he_cur in ("1", "true", "yes")
            and wr_cur
        ):
            print(
                f"  {Colors.success('Host executor + work root already set for browser automation (.env).')}"
            )
            print(f"  {Colors.info(f'Workspace path: {wr_cur}')}")
            if _aethos_auto_register_workspace_default():
                self.pending_workspace = (wr_cur, "setup_workspace")
                print(
                    f"  {Colors.success('Will register this path via API when the API is up (AETHOS_AUTO_REGISTER_WORKSPACE).')}"
                )
            else:
                reg = prompt_line(
                    f"  {Colors.question(f'Register {wr_cur} as a Mission Control workspace root when the API is up? [Y/n]')} "
                ).strip().lower()
                if reg in ("", "y", "yes"):
                    self.pending_workspace = (wr_cur, "setup_workspace")
                    print(
                        f"  {Colors.info('Will POST /api/v1/web/workspace/roots during verification if the API responds.')}"
                    )
            return True

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
        print(f"  {Colors.info(f'Workspace path: {resolved}')}")
        if _aethos_auto_register_workspace_default():
            self.pending_workspace = (resolved, "setup_workspace")
            print(
                f"  {Colors.success('Will register this path via API when the API is up (AETHOS_AUTO_REGISTER_WORKSPACE).')}"
            )
        else:
            reg = prompt_line(
                f"  {Colors.question(f'Register {resolved} as a Mission Control workspace root when the API is up? [Y/n]')} "
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

    def _find_web_dir(self) -> Path | None:
        """Locate the Mission Control / Next.js app directory."""
        candidates = [
            self.repo_root / "web",
            self.repo_root / "frontend",
            self.repo_root / "mission-control",
            self.repo_root / "ui",
        ]
        for cand in candidates:
            if cand.is_dir() and (cand / "package.json").is_file():
                return cand
        return None

    def _is_port_in_use(self, port: int) -> bool:
        free, _msg = Validator.check_port(port)
        return not free

    def _kill_process_on_port(self, port: int) -> bool:
        """Best-effort: stop listeners on ``port`` (macOS/Linux ``lsof``)."""
        if not shutil.which("lsof"):
            return False
        try:
            result = subprocess.run(
                ["lsof", "-ti", f":{port}"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            pids = [p for p in result.stdout.strip().split() if p.isdigit()]
            if not pids:
                return False
            for pid in pids:
                subprocess.run(["kill", "-9", pid], capture_output=True, timeout=5)
            time.sleep(0.4)
            return True
        except (OSError, subprocess.TimeoutExpired):
            return False

    def _wait_http_ok(self, url: str, *, max_seconds: float = 60.0, interval: float = 0.5) -> bool:
        """Poll until ``url`` returns HTTP 2xx or 3xx."""
        deadline = time.monotonic() + max_seconds
        while time.monotonic() < deadline:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "AethOS-setup/1"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    code = int(resp.status)
                    if 200 <= code < 400:
                        return True
            except urllib.error.HTTPError as e:
                if 200 <= int(e.code) < 400:
                    return True
            except Exception:
                pass
            time.sleep(interval)
        return False

    def _should_auto_open_browser(self) -> bool:
        if self.no_browser:
            return False
        if (os.environ.get("AETHOS_SETUP_NO_BROWSER") or "").strip().lower() in ("1", "true", "yes"):
            return False
        if (os.environ.get("CI") or "").strip() or (os.environ.get("GITHUB_ACTIONS") or "").strip():
            return False
        return True

    def _open_mission_control_browser(self, web_port: int) -> None:
        url = f"http://localhost:{web_port}"
        if not self._should_auto_open_browser():
            print(
                f"  {Colors.DIM}Browser auto-open skipped (CI, --no-browser, or AETHOS_SETUP_NO_BROWSER=1).{Colors.RESET}"
                f"\n  {Colors.DIM}Open manually: {url}{Colors.RESET}"
            )
            return
        print(f"  {Colors.info(f'Opening browser → {url}')}")
        opened = False
        try:
            opened = bool(webbrowser.open(url))
        except Exception:
            opened = False
        if not opened and sys.platform == "darwin":
            subprocess.run(["open", url], check=False, timeout=20)
        elif not opened and sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", url], check=False, timeout=20)
        elif not opened and os.name == "nt":
            subprocess.run(["cmd", "/c", "start", "", url], check=False, timeout=20)

    def _build_web_ui(self, web_dir: Path) -> bool:
        """Run ``npm install`` and ``npm run build`` when a build script exists."""
        if not web_dir.is_dir() or not shutil.which("npm"):
            if not shutil.which("npm"):
                print(f"  {Colors.warning('npm not found — install Node.js to build Mission Control')}")
            return False

        print(f"  {Colors.info(f'Installing web dependencies in {web_dir.name}/ …')}")
        npm_install = subprocess.run(
            ["npm", "install"],
            cwd=str(web_dir),
            capture_output=True,
            text=True,
            timeout=900,
        )
        if npm_install.returncode != 0:
            tail = (npm_install.stderr or npm_install.stdout or "")[-400:]
            print(f"  {Colors.warning('npm install failed — Mission Control may not run')}")
            if tail.strip():
                print(f"  {Colors.DIM}{tail.strip()}{Colors.RESET}")
            return False

        pkg_path = web_dir / "package.json"
        if not pkg_path.is_file():
            return True
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return True
        if "build" not in (pkg.get("scripts") or {}):
            return True

        print(f"  {Colors.info('Running npm run build …')}")
        build = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(web_dir),
            capture_output=True,
            text=True,
            timeout=900,
        )
        if build.returncode != 0:
            tail = (build.stderr or build.stdout or "")[-400:]
            print(f"  {Colors.warning('npm run build failed — dev server may still work')}")
            if tail.strip():
                print(f"  {Colors.DIM}{tail.strip()}{Colors.RESET}")
            return False
        print(f"  {Colors.success('Web production build finished')}")
        return True

    def _auto_free_listen_ports(self, ports: set[int]) -> None:
        """Stop listeners on common dev ports so API / Mission Control can bind (best-effort)."""
        if (os.environ.get("AETHOS_SETUP_NO_KILL_PORTS") or "").strip().lower() in ("1", "true", "yes"):
            return
        for p in sorted(ports):
            if not self._is_port_in_use(p):
                continue
            print(f"  {Colors.info(f'Port {p} is in use — stopping existing listener(s)…')}")
            self._kill_process_on_port(p)

    def _start_web_ui(self, web_dir: Path, *, web_port: int = 3000) -> bool:
        """Start ``npm run dev`` for Mission Control in the background."""
        if not shutil.which("npm"):
            return False
        print(f"  {Colors.info(f'Starting Mission Control (npm run dev) on port {web_port}…')}")

        self._auto_free_listen_ports({web_port})
        if self._is_port_in_use(web_port):
            print(
                f"  {Colors.DIM}Manual: cd {web_dir} && npm run dev{Colors.RESET}"
            )
            return False

        log_dir = self.repo_root / ".setup"
        log_dir.mkdir(parents=True, exist_ok=True)
        web_log = open(log_dir / "web.setup.log", "ab", buffering=0)
        popen_kw: dict[str, Any] = {
            "args": ["npm", "run", "dev"],
            "cwd": str(web_dir),
            "stdout": web_log,
            "stderr": subprocess.STDOUT,
            "env": {**os.environ, **self._env_for_subprocess(), "PORT": str(web_port)},
        }
        if os.name != "nt":
            popen_kw["start_new_session"] = True
        self._web_process = subprocess.Popen(**popen_kw)

        for _ in range(20):
            time.sleep(0.5)
            if self._is_port_in_use(web_port):
                break
        else:
            print(f"  {Colors.warning('Mission Control did not bind a port — see .setup/web.setup.log')}")
            return False

        print(f"  {Colors.info('Waiting for Mission Control HTTP (up to 60s)…')}")
        if not self._wait_http_ok(f"http://127.0.0.1:{web_port}/", max_seconds=60.0):
            print(f"  {Colors.warning('Mission Control did not respond in time — see .setup/web.setup.log')}")
            return False
        print(f"  {Colors.success(f'Mission Control ready — http://localhost:{web_port}')}")
        return True

    def _write_aethos_setup_creds_file(self, api_base: str | None = None) -> None:
        """Write JSON for Mission Control / Next to auto-load (``AETHOS_SETUP_CREDS_FILE`` overrides path)."""
        ab = (api_base or self._get_env_value("API_BASE_URL") or "http://127.0.0.1:8010").rstrip("/")
        uid = (
            (self._get_env_value("TEST_X_USER_ID") or self._get_env_value("X_USER_ID") or "").strip()
        )
        tok = (self._get_env_value("NEXA_WEB_API_TOKEN") or "").strip()
        if not uid or not tok:
            return
        try:
            sys.path.insert(0, str(self.repo_root))
            from app.core.setup_creds_file import merge_setup_creds, setup_creds_json_path

            merge_setup_creds(api_base=ab, user_id=uid or None, bearer_token=tok or None)
            dest = setup_creds_json_path()
            if dest.is_file() and dest.stat().st_size > 0:
                print(f"  {Colors.success(f'Mission Control bootstrap creds → {dest}')}")
        except Exception as exc:  # noqa: BLE001
            print(f"  {Colors.warning(f'Could not write setup creds file: {exc!s}')}")
        self._register_workspace_roots_via_api(ab)

    def _wait_api_health_ok(self, api_base: str, *, max_wait_sec: int = 30) -> bool:
        """Poll ``/api/v1/health`` until success or timeout (best-effort)."""
        health = f"{api_base.rstrip('/')}/api/v1/health"
        deadline = time.time() + float(max_wait_sec)
        while time.time() < deadline:
            try:
                req = urllib.request.Request(health)
                with urllib.request.urlopen(req, timeout=3) as resp:
                    if resp.status < 500:
                        return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def _register_workspace_roots_via_api(self, api_base: str) -> None:
        """POST ``NEXA_WORKSPACE_ROOT`` (or pending wizard path) so agents see a registered root."""
        if self._workspace_register_done:
            return
        token = (self._get_env_value("NEXA_WEB_API_TOKEN") or "").strip()
        web_user = (
            (self._get_env_value("TEST_X_USER_ID") or self._get_env_value("X_USER_ID") or "").strip()
            or "web_setup_wizard"
        )
        if not token:
            print(
                f"  {Colors.warning('Skipping workspace API registration (NEXA_WEB_API_TOKEN missing)')}"
            )
            return
        ab = api_base.rstrip("/")
        if not self._wait_api_health_ok(ab, max_wait_sec=30):
            print(
                f"  {Colors.warning('API not reachable yet — workspace registration skipped (retry after API is up)')}"
            )
            return
        if self.pending_workspace:
            path, label = self.pending_workspace
        else:
            path = (self._get_env_value("NEXA_WORKSPACE_ROOT") or "").strip()
            if not path:
                path = str(Path.home() / "aethos-workspace")
            label = "env_workspace"
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            print(f"  {Colors.warning(f'Could not create workspace directory {path!s}: {exc}')}")
            return
        url = f"{ab}/api/v1/web/workspace/roots"
        body = json.dumps({"path": path, "label": label}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("X-User-Id", web_user)
        req.add_header("Authorization", f"Bearer {token}")
        try:
            urllib.request.urlopen(req, timeout=20)
            print(
                f"  {Colors.success(f'Workspace root registered via API ({path})')}"
            )
            self._workspace_register_done = True
            self.pending_workspace = None
        except urllib.error.HTTPError as e:
            print(
                f"  {Colors.warning(f'Workspace registration HTTP {e.code} — add the root in Mission Control if needed.')}"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  {Colors.warning(f'Workspace registration skipped: {exc!s}')}")

    def start_services(self) -> bool:
        print(f"\n{Colors.step(8, TOTAL_STEPS, 'Starting services (API + Mission Control)…')}\n")
        if self.skip_services:
            print(f"  {Colors.info('Skipped (--skip-services)')}")
            self._write_aethos_setup_creds_file()
            return True

        api_base = self._get_env_value("API_BASE_URL") or "http://127.0.0.1:8010"
        port = parse_port_from_api_base(api_base)
        web_port = 3000

        self._auto_free_listen_ports({port, web_port, 8000, 8010})

        if self._is_port_in_use(port):
            print(f"  {Colors.warning(f'API port {port} is still in use after cleanup — check lsof or pick another port in .env')}")
            print(
                f"  {Colors.DIM}Manual: {sys.executable} -m uvicorn app.main:app --host 0.0.0.0 --port {port}{Colors.RESET}"
            )
            self._write_aethos_setup_creds_file(api_base.rstrip("/"))
            return True

        print(f"  {Colors.info(f'Starting API on port {port} (logs: .setup/uvicorn.setup.log)')}")
        log_dir = self.repo_root / ".setup"
        log_dir.mkdir(parents=True, exist_ok=True)
        out_log = open(log_dir / "uvicorn.setup.log", "ab", buffering=0)
        api_env = {
            **os.environ,
            **self._env_for_subprocess(),
            "PYTHONPATH": str(self.repo_root) + os.pathsep + os.environ.get("PYTHONPATH", ""),
        }
        popen_api: dict[str, Any] = {
            "args": [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
            ],
            "cwd": str(self.repo_root),
            "stdout": out_log,
            "stderr": subprocess.STDOUT,
            "env": api_env,
        }
        if os.name != "nt":
            popen_api["start_new_session"] = True
        self._api_process = subprocess.Popen(**popen_api)
        (log_dir / "uvicorn.setup.pid").write_text(str(self._api_process.pid), encoding="utf-8")

        health_url = f"{api_base.rstrip('/')}/api/v1/health"
        print(f"  {Colors.info('Waiting for API health (up to 60s)…')}")
        if not self._wait_http_ok(health_url, max_seconds=60.0):
            print(f"  {Colors.warning('API did not become healthy in time — see .setup/uvicorn.setup.log')}")
            return False
        print(f"  {Colors.success(f'API healthy — http://127.0.0.1:{port} (docs: /docs)')}")

        web_dir = self._find_web_dir()
        mission_ok = False
        if web_dir and (web_dir / "package.json").is_file():
            print(f"\n  {Colors.info('Mission Control (Web UI)')}")
            self._build_web_ui(web_dir)
            mission_ok = bool(self._start_web_ui(web_dir, web_port=web_port))
            if mission_ok:
                self._open_mission_control_browser(web_port)
        else:
            print(
                f"  {Colors.DIM}Web UI directory not found — skipped (expected web/ with package.json){Colors.RESET}"
            )

        self._write_aethos_setup_creds_file(api_base.rstrip("/"))
        return True

    def verify_installation(self) -> bool:
        print(f"\n{Colors.step(9, TOTAL_STEPS, 'Verifying installation…')}\n")
        api_base = (self._get_env_value("API_BASE_URL") or "http://127.0.0.1:8010").rstrip("/")

        token = (self._get_env_value("NEXA_WEB_API_TOKEN") or "").strip()
        web_user = (
            (self._get_env_value("TEST_X_USER_ID") or self._get_env_value("X_USER_ID") or "").strip()
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
                self._register_workspace_roots_via_api(api_base)
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
        """Set ``key``; removes every duplicate assignment line for ``key`` then writes one row."""
        self.env_path.parent.mkdir(parents=True, exist_ok=True)
        lines: list[str] = []
        if self.env_path.is_file():
            lines = self.env_path.read_text(encoding="utf-8").splitlines()
        new_lines: list[str] = []
        inserted = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#") or "=" not in line:
                new_lines.append(line)
                continue
            k, _, _ = line.partition("=")
            if k.strip() == key:
                if not inserted:
                    new_lines.append(f"{key}={value}")
                    inserted = True
                continue
            new_lines.append(line)
        if not inserted:
            new_lines.append(f"{key}={value}")
        self.env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    def _get_env_value(self, key: str) -> str | None:
        if not self.env_path.is_file():
            return None
        last: str | None = None
        for line in self.env_path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            if k.strip() == key:
                last = v.strip().strip('"').strip("'")
        return last

    # --- flow ---

    def prompt_overwrite(self) -> bool:
        print(f"\n{Colors.warning('Existing configuration detected (.env present).')}")
        print(f"  {Colors.DIM}A backup will be written before changes.{Colors.RESET}")
        out = prompt_line(f"\n{Colors.question('Re-run full setup (override)? [y/N]')} ").strip().lower()
        return out == "y"

    def run(self) -> None:
        display_legal_notice(force=self.force, accept_disclaimer=self.accept_disclaimer)
        reattach_tty_stdin_if_needed()
        self.print_banner()
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
            ("services", "Start API & Mission Control", self.start_services),
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
        web_port = 3000
        connect_uid = (
            (self._get_env_value("TEST_X_USER_ID") or self._get_env_value("X_USER_ID") or "").strip()
            or "web_setup_user"
        )
        full_tok = (self._get_env_value("NEXA_WEB_API_TOKEN") or "").strip()
        if len(full_tok) > 42:
            tok_show = f"{full_tok[:24]}…{full_tok[-8:]}"
        elif full_tok:
            tok_show = full_tok
        else:
            tok_show = "(set NEXA_WEB_API_TOKEN in .env)"

        print(
            f"""
{Colors.GREEN}✅ AethOS is now installed and running!{Colors.RESET}

{Colors.BOLD}🌐 Access your Agentic OS:{Colors.RESET}

  {Colors.CYAN}Mission Control (Web UI):{Colors.RESET}
     → {Colors.BOLD}http://localhost:{web_port}{Colors.RESET}

  {Colors.CYAN}API:{Colors.RESET}
     → {Colors.BOLD}http://127.0.0.1:{port}{Colors.RESET}
     → {Colors.DIM}API docs: http://127.0.0.1:{port}/docs{Colors.RESET}

{Colors.BOLD}📋 Connection (Mission Control auto-fills from the API when local):{Colors.RESET}
  • API Base URL: {Colors.BOLD}http://127.0.0.1:{port}{Colors.RESET}
  • Bearer token: {Colors.BOLD}{tok_show}{Colors.RESET}
  • X-User-Id: {Colors.BOLD}{connect_uid}{Colors.RESET}

{Colors.DIM}If a field is empty, open Login — the app calls /api/setup-creds using your repo .env.{Colors.RESET}

{Colors.BOLD}💡 Next steps:{Colors.RESET}
  • If the browser did not open, visit {Colors.CYAN}http://localhost:{web_port}{Colors.RESET}
  • In Mission Control, try: {Colors.CYAN}create a marketing agent{Colors.RESET}

{Colors.DIM}Credentials: {CREDS_FILE_HOME}{Colors.RESET}
{Colors.DIM}Logs: .setup/uvicorn.setup.log · .setup/web.setup.log{Colors.RESET}
{Colors.DIM}Also see .env.example and repo docs/.{Colors.RESET}
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
        help="Do not start uvicorn or Mission Control (npm dev)",
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
        help="Acknowledge LICENSE.disclaimer without interactive prompt (optional; non-TTY/CI auto-accepts)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not auto-open Mission Control in the default browser after setup",
    )
    parser.add_argument(
        "--skip-playwright-browsers",
        action="store_true",
        help="Skip Playwright Chromium download and browser .env prompts (CI/headless images)",
    )
    parser.add_argument(
        "--home-env",
        action="store_true",
        help="Write ~/.aethos/.env instead of <repo>/.env (one-machine / one-curl style)",
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
        no_browser=args.no_browser,
        skip_playwright_browsers=args.skip_playwright_browsers,
        use_home_env=args.home_env,
    )
    try:
        wizard.run()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.warning('Setup cancelled')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
