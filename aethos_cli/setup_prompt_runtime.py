# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Interactive setup prompt runtime — global commands on every prompt (Phase 4 Step 17)."""

from __future__ import annotations

from typing import Any, Callable

from aethos_cli.setup_conversational import SETUP_GLOBAL_COMMANDS, calm_provider_validation_failed
from aethos_cli.setup_progress_state import build_progress_status, load_setup_progress, mark_section, save_setup_progress
from aethos_cli.ui import print_box, print_info, print_warn

_STEP_WHY: dict[str, str] = {
    "default": "This step configures how AethOS orchestrates your operational environment.",
    "llm": "Providers are interchangeable reasoning engines — AethOS routes work advisory-first.",
    "workspace": "The workspace is where projects and automation execute under orchestrator policy.",
    "directory": "AethOS needs a stable install path for dependencies and configuration.",
}


class SetupPromptContext:
    def __init__(self, *, section: str = "welcome", last_prompt: str = "", secrets: dict[str, str] | None = None):
        self.section = section
        self.last_prompt = last_prompt
        self.secrets = secrets or {}
        self.recommended_defaults: dict[str, str] = {}
        self._back_stack: list[str] = []

    def set_recommended(self, key: str, value: str) -> None:
        self.recommended_defaults[key] = value


_CTX = SetupPromptContext()


def set_prompt_context(**kwargs: Any) -> None:
    global _CTX
    for k, v in kwargs.items():
        if hasattr(_CTX, k):
            setattr(_CTX, k, v)


def prompt_setup(
    label: str,
    default: str | None = None,
    *,
    hide: bool = False,
    recommended: str | None = None,
    allow_skip: bool = True,
    get_input_fn: Callable[..., str] | None = None,
) -> str:
    """Prompt until a non-command answer or quit."""
    from aethos_cli.ui import get_input as _ui_get_input

    reader = get_input_fn or _ui_get_input
    _CTX.last_prompt = label
    save_setup_progress(current_section=_CTX.section, last_prompt=label)
    rec = recommended or _CTX.recommended_defaults.get(label) or default

    while True:
        raw = reader(label, rec if not hide else default, hide=hide)
        cmd = raw.strip().lower()
        if cmd in SETUP_GLOBAL_COMMANDS:
            action = _handle_command(cmd, label=label, default=default, recommended=rec, allow_skip=allow_skip, hide=hide)
            if action == "quit":
                save_setup_progress()
                raise SystemExit(0)
            if action == "skip":
                if allow_skip:
                    mark_section(_CTX.section, skipped=True)
                    return ""
                print_warn("This step is required — use recommended or enter a value.")
                continue
            if action == "recommended":
                if rec:
                    return rec
                print_info("No recommendation for this prompt — using default if set.")
                continue
            if action == "use_default" and default is not None:
                return default
            continue
        return raw


def _handle_command(
    cmd: str,
    *,
    label: str,
    default: str | None,
    recommended: str | None,
    allow_skip: bool,
    hide: bool,
) -> str:
    if cmd == "help":
        print_box(
            f"Help — {_CTX.section}",
            [
                f"Prompt: {label}",
                "Commands: " + " · ".join(SETUP_GLOBAL_COMMANDS),
                "why — purpose of this step",
                "status — setup progress",
                "recommended — use suggested value",
                "quit — save and exit",
            ],
        )
        return "continue"
    if cmd == "why":
        key = "llm" if "llm" in label.lower() or "api" in label.lower() or "key" in label.lower() else _CTX.section
        print_info(_STEP_WHY.get(key, _STEP_WHY["default"]))
        return "continue"
    if cmd == "status":
        st = build_progress_status()
        print_box(
            "Setup status",
            [
                f"Current: {st.get('current_section')}",
                f"Completed: {', '.join(st.get('completed_sections') or []) or '—'}",
                f"Pending: {', '.join(st.get('pending_sections') or []) or '—'}",
                f"Failed: {', '.join(st.get('failed_sections') or []) or '—'}",
            ],
        )
        return "continue"
    if cmd == "resume":
        p = load_setup_progress()
        print_info(f"Resume from section: {p.get('current_section') or 'welcome'}")
        return "continue"
    if cmd == "current":
        if hide:
            print_info("Value is hidden (secret). Configured in saved setup state.")
        elif default:
            print_info(f"Current/default: {default}")
        else:
            print_info("No value saved yet for this prompt.")
        for k, v in _CTX.secrets.items():
            if k in label.lower():
                print_info(f"{k}: {'***' if hide else v}")
        return "continue"
    if cmd == "recommended":
        if recommended:
            return "recommended"
        print_info("No recommendation — try default or enter manually.")
        return "continue"
    if cmd == "repair":
        try:
            from aethos_cli.setup_wizard import run_setup_wizard

            print_info("Starting setup repair…")
            run_setup_wizard(install_kind="repair")
        except Exception:
            print_info("Run: aethos setup repair  or  aethos doctor")
        return "continue"
    if cmd == "back":
        print_info("Back is limited in this wizard — use quit and `aethos setup resume`.")
        return "continue"
    if cmd == "skip":
        return "skip" if allow_skip else "continue"
    if cmd == "quit":
        return "quit"
    return "continue"


def prompt_select(
    prompt: str,
    options: list[tuple[str, str, str]],
    *,
    default_index: int = 1,
) -> str:
    """Menu select with global setup commands on each line."""
    import sys

    from aethos_cli.setup_interactive_mode import noninteractive_setup, setup_interactive

    if noninteractive_setup() or not (sys.stdin.isatty() or setup_interactive()):
        di = default_index if 1 <= default_index <= len(options) else 1
        return options[di - 1][1]

    print(f"\n   {prompt}")
    for i, (label, _value, desc) in enumerate(options, 1):
        extra = f" — {desc}" if desc else ""
        print(f"   [{i}] {label}{extra}")
    print_info("Commands: " + " · ".join(SETUP_GLOBAL_COMMANDS))
    while True:
        raw = prompt_setup(f"Choice (default {default_index})", str(default_index), allow_skip=False)
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1][1]
            print_warn(f"Enter a number from 1 to {len(options)}.")
            continue
        if not raw.strip():
            di = default_index if 1 <= default_index <= len(options) else 1
            return options[di - 1][1]


def prompt_confirm(question: str, default: bool = True) -> bool:
    from aethos_cli.ui import confirm as _confirm

    while True:
        raw = prompt_setup(f"{question} (y/n)", "y" if default else "n", allow_skip=False)
        low = raw.strip().lower()
        if low in ("y", "yes", "1", "true"):
            return True
        if low in ("n", "no", "0", "false"):
            return False
        if not raw.strip():
            return _confirm(question, default=default)
        print_warn("Answer y or n, or use help.")


__all__ = ["prompt_setup", "prompt_select", "prompt_confirm", "set_prompt_context", "SetupPromptContext"]
