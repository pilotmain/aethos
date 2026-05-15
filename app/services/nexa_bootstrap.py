# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
One-command setup: detect environment, create .env, venv, optional Docker stack, health check.
:func:`main` is the entry for ``python scripts/nexa_bootstrap.py``. No secret values in stdout.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import os
import platform
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# Repo: app/services/nexa_bootstrap.py -> app -> project
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HEALTH_PATH = "/api/v1/health"
DOCKER_ENV_TEMPLATE = "env.docker.example"
MARKER = "# ——— Nexa bootstrap (defaults) ———"

DEFAULTS_LINES = (
    "POSTGRES_HOST_PORT=5434\n"
    "DEV_EXECUTOR_ON_HOST=1\n"
    "OPERATOR_AUTO_RUN_DEV_EXECUTOR=false\n"
    "# Phase 54 — privacy-first defaults (override intentionally)\n"
    "NEXA_LOCAL_FIRST=true\n"
    "NEXA_STRICT_PRIVACY_MODE=true\n"
    "NEXA_BLOCK_OVER_TOKEN_BUDGET=true\n"
    "NEXA_TOKEN_BUDGET_PER_REQUEST=8000\n"
    "NEXA_NETWORK_EGRESS_MODE=allowlist\n"
)
PACKAGE_IMPORT = {
    "cryptography": "cryptography",
    "pydantic": "pydantic",
    "sqlalchemy": "sqlalchemy",
    "psycopg2-binary": "psycopg2",
    "httpx": "httpx",
    "openai": "openai",
    "anthropic": "anthropic",
}


def detect_environment() -> dict:
    d = "docker" if Path("/.dockerenv").is_file() else "host"
    py = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    venv = (REPO_ROOT / ".venv").is_dir()
    has_d = shutil.which("docker") is not None
    in_use_5434 = _tcp_listening("127.0.0.1", 5434)
    return {
        "mode": d,
        "os": platform.system().lower(),
        "python": py,
        "venv": venv,
        "docker": has_d,
        "postgres_5434_open": in_use_5434,
    }


def _tcp_listening(host: str, port: int) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.35)
        s.connect((host, port))
        s.close()
        return True
    except OSError:
        return False


def _new_secret() -> str:
    return secrets.token_urlsafe(40)


def _append_bootstrap_footer(text: str) -> str:
    if MARKER in text:
        return text
    sec = _new_secret()
    return (
        text.rstrip()
        + "\n\n"
        + MARKER
        + "\n"
        + f"NEXA_SECRET_KEY={sec}\n"
        + DEFAULTS_LINES
        + "\n"
    )


def _normalize_docker_template_copy(text: str) -> str:
    out = re.sub(
        r"^OPERATOR_AUTO_RUN_DEV_EXECUTOR\s*=\s*.*$",
        "OPERATOR_AUTO_RUN_DEV_EXECUTOR=false",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if "OPERATOR_AUTO_RUN_DEV_EXECUTOR" not in out:
        out = out.rstrip() + "\nOPERATOR_AUTO_RUN_DEV_EXECUTOR=false\n"
    out = re.sub(
        r"^#?\s*POSTGRES_HOST_PORT\s*=\s*.*$",
        "POSTGRES_HOST_PORT=5434",
        out,
        flags=re.MULTILINE,
    )
    if not re.search(r"^POSTGRES_HOST_PORT\s*=\s*5434\s*$", out, re.MULTILINE):
        if re.search(r"^POSTGRES_HOST_PORT\s*=", out, re.MULTILINE):
            out = re.sub(
                r"^POSTGRES_HOST_PORT\s*=\s*[^\n#]*",
                "POSTGRES_HOST_PORT=5434",
                out,
                count=1,
                flags=re.MULTILINE,
            )
        else:
            out = out.rstrip() + "\nPOSTGRES_HOST_PORT=5434\n"
    if "DEV_EXECUTOR_ON_HOST" not in out:
        out = out.rstrip() + "\nDEV_EXECUTOR_ON_HOST=1\n"
    return out


def _env_template_path(root: Path) -> Path | None:
    for name in (".env.example", DOCKER_ENV_TEMPLATE):
        p = root / name
        if p.is_file():
            return p
    return None


def _parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, _, v = s.partition("=")
        key = k.strip()
        if key:
            out[key] = v.strip()
    return out


def _meaningful_env_value(val: str) -> bool:
    v = (val or "").strip()
    if not v:
        return False
    if "CHANGE_ME" in v.upper():
        return False
    return True


def _apply_preserved_env_values(template_text: str, preserved: dict[str, str]) -> str:
    if not preserved:
        return template_text
    lines: list[str] = []
    for line in template_text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in line:
            lines.append(line)
            continue
        k, _, _ = line.partition("=")
        key = k.strip()
        old = preserved.get(key)
        if old is not None and _meaningful_env_value(old):
            lines.append(f"{key}={old}")
        else:
            lines.append(line)
    text = "\n".join(lines)
    if template_text.endswith("\n"):
        text += "\n"
    return text


def _ensure_generated_secrets(text: str) -> str:
    out = text
    if not re.search(r"^NEXA_SECRET_KEY=", out, re.MULTILINE):
        return _append_bootstrap_footer(out)
    if re.search(r"^NEXA_SECRET_KEY=CHANGE_ME", out, re.MULTILINE | re.IGNORECASE):
        out = re.sub(
            r"^NEXA_SECRET_KEY=CHANGE_ME[^\n]*",
            f"NEXA_SECRET_KEY={_new_secret()}",
            out,
            count=1,
            flags=re.MULTILINE | re.IGNORECASE,
        )
    if MARKER not in out:
        out = _append_bootstrap_footer(out)
    return out


def sync_env_file(root: Path, *, force: bool = False) -> tuple[bool, str]:
    """
    Create or refresh ``.env`` from ``.env.example`` (host-first) or ``env.docker.example``.

    When ``force`` is true, existing non-placeholder values are preserved (API keys, tokens).
    """
    dest = root / ".env"
    preserved = _parse_env_file(dest) if dest.is_file() else {}
    if dest.is_file() and not force:
        return False, "unchanged"

    tpl = _env_template_path(root)
    if tpl is None:
        data = f"{MARKER}\n" + f"NEXA_SECRET_KEY={_new_secret()}\n" + DEFAULTS_LINES
    elif tpl.name == DOCKER_ENV_TEMPLATE:
        raw = tpl.read_text(encoding="utf-8", errors="replace")
        data = _normalize_docker_template_copy(raw)
    else:
        data = tpl.read_text(encoding="utf-8", errors="replace")

    if preserved:
        data = _apply_preserved_env_values(data, preserved)
    data = _ensure_generated_secrets(data)
    dest.write_text(data, encoding="utf-8")
    if force and preserved:
        return True, "refreshed"
    return True, "created"


def create_env_file_if_missing(root: Path) -> tuple[bool, str]:
    """Backward-compatible wrapper — does not overwrite an existing file."""
    return sync_env_file(root, force=False)


def ensure_venv_with_deps(root: Path) -> str:
    vdir = root / ".venv"
    if not vdir.is_dir():
        p = subprocess.run(
            [sys.executable, "-m", "venv", str(vdir)], cwd=root, timeout=180, check=False
        )
        if p.returncode != 0:
            return "venv_create_failed"
    pip = vdir / "bin" / "pip"
    if not pip.is_file() and (vdir / "bin" / "pip3").is_file():
        pip = vdir / "bin" / "pip3"
    if not pip.is_file():
        return "no_pip"
    p = subprocess.run(
        [str(pip), "install", "-r", str(root / "requirements.txt"), "-q"],
        cwd=root,
        timeout=900,
        check=False,
    )
    if p.returncode != 0:
        return "pip_install_incomplete"
    for _, im in PACKAGE_IMPORT.items():
        if im == "psycopg2":
            try:
                if importlib.util.find_spec("psycopg2") is None:
                    raise RuntimeError
            except (RuntimeError, OSError, ValueError):
                subprocess.run(
                    [str(pip), "install", "psycopg2-binary", "-q"],
                    cwd=root,
                    timeout=300,
                    check=False,
                )
    return "ok"


def check_aider() -> bool:
    return bool(shutil.which("aider") or shutil.which("aider-chat"))


def _run_docker_start(root: Path) -> int:
    sh = root / "run_everything.sh"
    if not sh.is_file():
        return 127
    p = subprocess.run(
        ["bash", str(sh), "start"],
        cwd=root,
        env={**os.environ},
        check=False,
        timeout=300,
    )
    return p.returncode


def wait_for_health(
    base_url: str, *, attempts: int = 30, sleep_s: float = 2.0
) -> bool:
    u = base_url.rstrip("/") + HEALTH_PATH
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(u, timeout=2) as r:  # nosec B310
                if (r.getcode() or 0) in (200, 204):
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        time.sleep(sleep_s)
    return False


def print_next_steps() -> None:
    print(
        "\nNext steps:\n"
        "1. Open Telegram\n"
        "2. Send /start to your bot\n"
        "3. Add an API key: /key set openai (paste your key from the provider)\n"
        "4. Ask a question. Use /access to see your capabilities.\n",
        flush=True,
    )


def run_bootstrap_cli_doctor() -> int:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    for line in (f"  platform: {platform.platform()}", f"  python: {sys.version}"):
        print(line, flush=True)
    d = detect_environment()
    for k, v in sorted(d.items()):
        print(f"  {k}: {v}", flush=True)
    if shutil.which("docker") is not None:
        s = subprocess.run(
            ["docker", "version"],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
        if s.returncode == 0:
            print("  docker: available", flush=True)
        else:
            print("  docker: not responding (is Docker running?)", flush=True)
    for pkg, im in PACKAGE_IMPORT.items():
        try:
            importlib.import_module(im)
        except (ImportError, OSError) as e:
            print(
                f"  missing import `{im}`. Try: pip install {pkg}\n" f"  ({e!s})",
                flush=True,
            )
    if (REPO_ROOT / ".env").is_file():
        from dotenv import load_dotenv

        load_dotenv(REPO_ROOT / ".env", override=True)
    try:
        from app.core.config import get_settings
        from app.core.db import SessionLocal, ensure_schema
        from app.services.env_validator import format_env_validation_report

        get_settings.cache_clear()
        ensure_schema()
        db = SessionLocal()
        try:
            t = format_env_validation_report()
            print("\n" + t + "\n", flush=True)
        finally:
            db.close()
    except (ImportError, OSError, RuntimeError) as e:
        print(f"doctor: could not load app env validation: {e!s}", flush=True)
    try:
        u = f"http://127.0.0.1:8000{HEALTH_PATH}"
        with urllib.request.urlopen(u, timeout=2) as r:  # nosec
            c = r.getcode()
        print(f"  API: HTTP {c} (GET {u})", flush=True)
    except (OSError, urllib.error.URLError) as e:
        print("  API: not reachable (start: ./run_everything.sh start)", flush=True)
        _ = e
    print(
        f"  project root: {str(REPO_ROOT)[:200]}",
        flush=True,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--doctor", action="store_true", help="Checks only; no .env or Docker start.")
    ap.add_argument(
        "--no-docker",
        action="store_true",
        help="Deprecated alias — Docker is off by default; use only with legacy scripts.",
    )
    ap.add_argument(
        "--with-docker",
        action="store_true",
        help="Start Postgres/API/bot via run_everything.sh (opt-in; default is host/SQLite).",
    )
    ap.add_argument(
        "--force-env",
        action="store_true",
        help="Refresh .env from .env.example; keep existing non-placeholder secrets.",
    )
    ns = ap.parse_args(argv)
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    if ns.doctor:
        return run_bootstrap_cli_doctor()
    if not sys.version_info >= (3, 10):
        print("Nexa recommends Python 3.10+.\n", flush=True)
    d = detect_environment()
    for k, v in sorted(d.items()):
        print(f"detect: {k}={v}", flush=True)
    c, st = sync_env_file(REPO_ROOT, force=bool(ns.force_env))
    if c and st == "refreshed":
        print(
            "Nexa: .env refreshed from template (existing API keys/tokens kept).\n",
            flush=True,
        )
    elif c:
        print("Nexa: .env was created. NEXA_SECRET_KEY is in the file (value not shown).\n", flush=True)
    else:
        print("Nexa: .env already exists; not overwriting (re-run with --force-env to refresh).\n", flush=True)
    s = ensure_venv_with_deps(REPO_ROOT)
    if s == "ok":
        print("Nexa: venv and requirements look good.\n", flush=True)
    else:
        print(
            f"Nexa: venv step: {s}. If needed: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt",
            "\n  pip install psycopg2-binary",
            "\n  pip install cryptography\n",
            flush=True,
        )
    if not check_aider():
        print("Aider not found. Dev agent will be limited (CLI/IDE handoff still work).\n", flush=True)
    if not ns.with_docker:
        print(
            "Host install: skipping Docker (SQLite default under ~/.aethos/data). "
            "Pass --with-docker only if you want the compose stack.\n",
            flush=True,
        )
        print_next_steps()
        return 0
    if not d.get("docker"):
        print(
            "Docker not in PATH. Use host mode (default) or install Docker and re-run with --with-docker.\n",
            flush=True,
        )
        print_next_steps()
        return 0
    r = _run_docker_start(REPO_ROOT)
    if r not in (0,):
        print("Nexa: run_everything.sh may still be building. Re-run or check: docker compose ps\n", flush=True)
    if wait_for_health("http://127.0.0.1:8000"):
        print("AethOS is ready. Open Telegram and message your bot.\n", flush=True)
    else:
        print(
            "Nexa: API not healthy yet. When the stack is up, check http://127.0.0.1:8000/api/v1/health and set TELEGRAM_BOT_TOKEN in .env if needed.\n",
            flush=True,
        )
    print_next_steps()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
