# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Terminal UI helpers for the Nexa CLI setup experience (Phase 25 / Phase 32).

Uses stdlib only (no Rich/Click) so ``pip install -r requirements.txt`` stays minimal.
"""

from __future__ import annotations

import getpass
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Sequence

NEXA_CLI_VERSION = "1.0.0"


def supports_color() -> bool:
    if not sys.stdout.isatty():
        return False
    return os_name_supports_ansi()


def os_name_supports_ansi() -> bool:
    return os.environ.get("TERM", "") not in ("", "dumb") or os.name == "nt"


class Colors:
    RESET = "\033[0m"
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    DIM = "\033[2m"


def _c(code: str, text: str) -> str:
    return f"{code}{text}{Colors.RESET}" if supports_color() else text


def print_header() -> None:
    """ASCII banner + tagline."""
    cyan = Colors.CYAN if supports_color() else ""
    reset = Colors.RESET if supports_color() else ""
    banner = rf"""
{cyan}╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ███╗   ██╗███████╗██╗  ██╗ █████╗                                         ║
║   ████╗  ██║██╔════╝╚██╗██╔╝██╔══██╗                                        ║
║   ██╔██╗ ██║█████╗   ╚███╔╝ ███████║                                        ║
║   ██║╚██╗██║██╔══╝   ██╔██╗ ██╔══██║                                        ║
║   ██║ ╚████║███████╗██╔╝ ██╗██║  ██║                                        ║
║   ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝                                        ║
║                                                                              ║
║                         Next-Gen AI Agent Framework                          ║
║                              v{NEXA_CLI_VERSION}                               ║
╚══════════════════════════════════════════════════════════════════════════════╝{reset}
"""
    print(banner, file=sys.stdout)


def print_environment_tag(pinfo_line: str) -> None:
    """📍 Environment line under banner (Phase 32)."""
    sym = _c(Colors.GREEN, "✅") if supports_color() else "OK"
    print(f"\n📍 Environment: {pinfo_line} {sym}\n")


def print_box(title: str, lines: list[str]) -> None:
    """Framed block (~77 cols) for step content (Phase 32)."""
    w = 77
    print("┌" + "─" * (w - 2) + "┐")
    print(f"│  {title}")
    print("├" + "─" * (w - 2) + "┤")
    for ln in lines:
        print(f"│  {ln}")
    print("└" + "─" * (w - 2) + "┘")


def disk_space_line(path: Path) -> tuple[str, bool]:
    """Returns '(~X.Y GB free of Z.Z GB)' and whether free >= need_gb."""
    need_gb = 0.5
    try:
        u = shutil.disk_usage(path)
        free_gb = u.free / (1024**3)
        total_gb = u.total / (1024**3)
        ok = free_gb >= need_gb
        return (
            f"Space available: ~{free_gb:.1f} GB (total ~{total_gb:.1f} GB)"
            + (" ✅" if ok else " ⚠️"),
            ok,
        )
    except OSError:
        return "Space available: (unknown)", True


def print_progress_bar(label: str, percent: int, *, width: int = 28) -> None:
    """ASCII progress bar 0–100."""
    percent = max(0, min(100, percent))
    filled = round(width * percent / 100)
    bar = "█" * filled + "░" * (width - filled)
    print(f"   {label} [{bar}] {percent}%")


def print_step(step: str, title: str) -> None:
    print(f"\n┌── {step} ─────────────────────────────────────────────────────────────")
    print(f"│  {title}")
    print("└────────────────────────────────────────────────────────────────────────")


def print_success(message: str) -> None:
    print(f"   {_c(Colors.GREEN, '✓')} {message}")


def print_error(message: str) -> None:
    print(f"   {_c(Colors.RED, '✗')} {message}", file=sys.stderr)


def print_info(message: str) -> None:
    print(f"   {_c(Colors.BLUE, 'ℹ')} {message}")


def print_warn(message: str) -> None:
    print(f"   {_c(Colors.YELLOW, '!')} {message}")


def confirm(question: str, default: bool = True) -> bool:
    yn = "Y/n" if default else "y/N"
    raw = input(f"   {question} [{yn}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "1", "true")


def select(
    prompt: str,
    options: Sequence[tuple[str, str, str]],
    *,
    default_index: int = 1,
) -> str:
    """Return the *value* (second element) of the chosen option (1-based menu)."""
    print(f"\n   {prompt}")
    for i, (label, _value, desc) in enumerate(options, 1):
        extra = f" — {desc}" if desc else ""
        print(f"   [{i}] {label}{extra}")
    while True:
        raw = input(f"   > (default {default_index}) ").strip()
        if not raw:
            idx = default_index
        else:
            try:
                idx = int(raw)
            except ValueError:
                print_warn("Enter a number from the list.")
                continue
        if 1 <= idx <= len(options):
            return options[idx - 1][1]
        print_warn("Invalid choice.")


def interactive_feature_toggle(
    title: str,
    options: Sequence[tuple[str, str, str]],
    *,
    default_enabled: Sequence[int] | None = None,
) -> list[str]:
    """
    Phase 32 — toggle features by number until user presses Enter on empty line.
    Shows [✓]/[ ] next to each option; type ``3`` + Enter to flip feature 3.
    """
    default_enabled = tuple(default_enabled or (1, 2, 3))
    n = len(options)
    on: set[int] = {i for i in default_enabled if 1 <= i <= n}

    def render() -> None:
        print(f"\n   {title}")
        print("   Enter a number to toggle that feature, or press Enter when done.\n")
        for i, (label, _value, desc) in enumerate(options, 1):
            mark = "✓" if i in on else " "
            extra = f" — {desc}" if desc else ""
            print(f"   [{mark}] [{i}] {label}{extra}")

    while True:
        render()
        raw = input("\n   Toggle # (empty = done): ").strip().lower()
        if not raw:
            break
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= n:
                if idx in on:
                    on.discard(idx)
                else:
                    on.add(idx)
            else:
                print_warn("Invalid number.")
        else:
            print_warn(f"Enter a single digit 1–{n}, or empty line to finish.")

    return [options[i - 1][1] for i in sorted(on)]


def multi_select_indices(
    prompt: str,
    options: Sequence[tuple[str, str, str]],
    *,
    default_enabled: Sequence[int] | None = None,
) -> list[str]:
    """
    Choose multiple features by index. ``default_enabled`` is 1-based indices initially on.

    User enters comma-separated numbers (e.g. ``1,2,3``) or ``all`` / ``none``.
    """
    default_enabled = tuple(default_enabled or (1, 2, 3))
    enabled = {i for i in default_enabled if 1 <= i <= len(options)}

    print(f"\n   {prompt}")
    print("   Enter comma-separated numbers to toggle on (e.g. 1,3,5), or 'all' / 'none'.")
    for i, (label, _value, desc) in enumerate(options, 1):
        on = "✓" if i in enabled else " "
        extra = f" — {desc}" if desc else ""
        print(f"   [{on}] [{i}] {label}{extra}")

    raw = input("   > ").strip().lower()
    if raw == "all":
        return [options[i][1] for i in range(len(options))]
    if raw == "none":
        return []
    if not raw:
        return [options[i - 1][1] for i in sorted(enabled)]

    out: set[str] = set()
    for part in raw.replace(",", " ").split():
        try:
            n = int(part.strip())
        except ValueError:
            continue
        if 1 <= n <= len(options):
            out.add(options[n - 1][1])
    return sorted(out)


def get_input(
    label: str,
    default: str | None = None,
    *,
    hide: bool = False,
) -> str:
    tail = f" [{default}]" if default else ""
    prompt = f"   {label}{tail}: "
    if hide:
        first = getpass.getpass(prompt)
        return first.strip() if first.strip() else (default or "").strip()
    line = input(prompt).strip()
    return line if line else (default or "")


def validate_openai_key(key: str) -> bool:
    if not key or not key.startswith("sk-"):
        return False
    try:
        import httpx

        r = httpx.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10.0,
        )
        return r.status_code == 200
    except Exception:
        return False


def validate_anthropic_key(key: str) -> bool:
    """Lightweight format check only (avoid billing on validate)."""
    if not key or len(key) < 20:
        return False
    return bool(re.match(r"^sk-ant-", key))


def validate_deepseek_key(key: str) -> bool:
    return bool(key and len(key.strip()) >= 8)


__all__ = [
    "NEXA_CLI_VERSION",
    "confirm",
    "disk_space_line",
    "get_input",
    "interactive_feature_toggle",
    "multi_select_indices",
    "print_box",
    "print_environment_tag",
    "print_error",
    "print_header",
    "print_info",
    "print_progress_bar",
    "print_step",
    "print_success",
    "print_warn",
    "select",
    "supports_color",
    "validate_anthropic_key",
    "validate_deepseek_key",
    "validate_openai_key",
]
