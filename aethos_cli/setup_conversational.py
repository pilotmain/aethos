# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Conversational setup copy and resume UX (Phase 4 Step 15)."""

from __future__ import annotations

import os
from pathlib import Path

from aethos_cli.ui import confirm, print_box, print_info, select


def _read_env_file(env_path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not env_path.is_file():
        return out
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            key, _, val = s.partition("=")
            out[key.strip()] = val.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def build_existing_config_summary(*, repo_root: Path) -> list[str]:
    """Human-readable summary of saved configuration."""
    env = _read_env_file(repo_root / ".env")
    mode = env.get("AETHOS_ROUTING_MODE") or os.environ.get("AETHOS_ROUTING_MODE") or "hybrid"
    pref = env.get("AETHOS_ROUTING_PREFERENCE") or "balanced"
    from aethos_cli.setup_routing import canonical_routing_label, canonical_routing_summary

    lines = [
        f"Strategy: {canonical_routing_label(mode)}",
        f"Routing: {canonical_routing_summary(mode, pref)}",
    ]
    local_model = env.get("NEXA_OLLAMA_MODEL") or env.get("OLLAMA_MODEL") or ""
    if local_model:
        lines.append(f"Local model: {local_model}")
    elif env.get("NEXA_OLLAMA_ENABLED", "").lower() in ("1", "true", "yes"):
        lines.append("Local model: Ollama enabled")
    providers: list[str] = []
    for key, label in (
        ("OPENAI_API_KEY", "OpenAI"),
        ("ANTHROPIC_API_KEY", "Anthropic"),
        ("GEMINI_API_KEY", "Gemini"),
        ("OPENROUTER_API_KEY", "OpenRouter"),
        ("DEEPSEEK_API_KEY", "DeepSeek"),
        ("GROQ_API_KEY", "Groq"),
        ("MISTRAL_API_KEY", "Mistral"),
    ):
        if env.get(key):
            providers.append(label)
    if providers:
        lines.append(f"Cloud providers: {', '.join(providers)}")
    else:
        lines.append("Cloud providers: not configured")
    ws = env.get("NEXA_WORKSPACE_ROOT") or str(Path.home() / "aethos-workspace")
    ws_path = Path(ws).expanduser()
    ws_count = 0
    if ws_path.is_dir():
        try:
            ws_count = sum(1 for p in ws_path.iterdir() if p.is_dir() and not p.name.startswith("."))
        except OSError:
            ws_count = 0
    lines.append(f"Workspace: {ws} ({ws_count} project folder{'s' if ws_count != 1 else ''})")
    mc_token = env.get("AETHOS_WEB_API_TOKEN") or env.get("NEXA_WEB_API_TOKEN")
    lines.append("Mission Control: configured" if mc_token else "Mission Control: not configured")
    if env.get("TELEGRAM_BOT_TOKEN"):
        lines.append("Telegram: connected")
    elif env.get("DISCORD_BOT_TOKEN"):
        lines.append("Discord: connected")
    else:
        lines.append("Channels: Web UI only")
    from aethos_cli.setup_onboarding_profile import load_onboarding_profile

    profile = load_onboarding_profile()
    if profile:
        name = profile.get("display_name") or profile.get("assistant_name") or "saved"
        lines.append(f"Onboarding profile: {name}")
    lines.append(f"Runtime health: {detect_runtime_health_label()}")
    return lines


def detect_runtime_operational(*, api_port: int = 8010) -> bool:
    """True when API health endpoint responds."""
    import socket

    try:
        with socket.create_connection(("127.0.0.1", api_port), timeout=0.4):
            pass
    except OSError:
        return False
    try:
        import urllib.request

        with urllib.request.urlopen(f"http://127.0.0.1:{api_port}/api/v1/health", timeout=2.0) as resp:
            return resp.status == 200
    except Exception:
        return False


def detect_runtime_health_label() -> str:
    port = int(os.environ.get("AETHOS_SERVE_PORT") or os.environ.get("NEXA_SERVE_PORT") or "8010")
    if detect_runtime_operational(api_port=port):
        return "healthy"
    if _port_in_use(port):
        return "starting"
    return "offline"


def _port_in_use(port: int) -> bool:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            return True
    except OSError:
        return False


def print_runtime_already_running_menu() -> str:
    """When runtime is already up. Returns: open | review | repair | restart | exit."""
    print_box(
        "AethOS is already running",
        [
            "Current environment is operational.",
            "You can open Mission Control, review configuration, repair, or restart services.",
        ],
    )
    return select(
        "What would you like to do?",
        [
            ("Open Mission Control", "open", "Browser launch via aethos open"),
            ("Review configuration", "review", "Step through setup sections"),
            ("Repair setup", "repair", "Reinstall deps and repair core keys"),
            ("Restart services", "restart", "Coordinate runtime restart"),
            ("Exit", "exit", "Leave runtime as-is"),
        ],
        default_index=0,
    )


def print_welcome_intro() -> None:
    print_box(
        "Welcome — I am AethOS",
        [
            "I am your orchestrator — not the thinking model itself.",
            "I will help you configure runtime, providers, Mission Control, workspace, and first-run preferences.",
            "Setup usually takes a few minutes.",
            "At any prompt you can type: help · why · back · status · repair · quit",
        ],
    )


def prompt_section_review(section_title: str, configured_lines: list[str]) -> str:
    """Return keep | change | skip."""
    print_box(f"Configured — {section_title}", configured_lines or ["(not configured yet)"])
    return select(
        f"Keep this {section_title.lower()} section?",
        [
            ("Keep", "keep", "Continue without changes"),
            ("Change", "change", "Reconfigure this section"),
            ("Skip for now", "skip", "Defer this section"),
        ],
        default_index=0,
    )


def print_existing_routing_review(*, mode: str, preference: str, mission_control: bool = False) -> str:
    """When routing already configured. Returns: keep | adjust | rebuild."""
    from aethos_cli.setup_routing import canonical_routing_label, canonical_routing_summary

    lines = [
        "AethOS already configured your local runtime routing.",
        "",
        "Current strategy:",
        f"• {canonical_routing_label(mode)}",
        f"• {canonical_routing_summary(mode, preference)}",
    ]
    if mission_control:
        lines.append("• Mission Control linked")
    print_box("Existing configuration", lines)
    return select(
        "Would you like to:",
        [
            ("Keep this configuration", "keep", "Continue setup with current routing"),
            ("Improve or adjust it", "adjust", "Re-run routing section"),
            ("Rebuild setup from scratch", "rebuild", "Clear wizard state"),
        ],
        default_index=0,
    )


def print_existing_setup_menu(*, repo_root: Path | None = None) -> str:
    """
    When install already exists.

    Returns: continue_review | keep_start | section | restart | repair
    """
    summary: list[str] = []
    if repo_root is not None:
        summary = build_existing_config_summary(repo_root=repo_root)
    body = ["AethOS found an existing setup.", ""]
    if summary:
        body.append("Current configuration:")
        body.extend(f"• {line}" for line in summary)
        body.append("")
    body.append("What would you like to do?")
    print_box("Existing setup", body)
    return select(
        "How would you like to proceed?",
        [
            ("Continue and review each section", "continue_review", "Step through setup interactively"),
            ("Keep current config and start AethOS", "keep_start", "Skip reconfiguration; offer startup"),
            ("Change one section", "section", "Pick a section to reconfigure"),
            ("Restart setup from scratch", "restart", "Clears saved wizard state"),
            ("Repair setup", "repair", "Reinstall deps and repair core keys"),
        ],
        default_index=0,
    )


def print_welcome_back_resume(*, repo_root: Path | None = None) -> str:
    """Ask how to continue after interruption."""
    print_info("Welcome back — setup was interrupted.")
    return print_existing_setup_menu(repo_root=repo_root)


def print_change_one_section_menu() -> str | None:
    """Return section id to re-run, or None to skip."""
    return select(
        "Which section would you like to change?",
        [
            ("Runtime strategy", "runtime_strategy", "Local / cloud / hybrid"),
            ("Providers & API keys", "providers", "LLM providers"),
            ("Channels", "channels", "Telegram and messaging"),
            ("Mission Control connection", "mission_control", "Bearer token and web env"),
            ("Workspace", "workspace", "Project workspace path"),
            ("Onboarding profile", "onboarding", "Operator preferences"),
            ("Web search", "web_search", "Search provider"),
            ("Integrations", "integrations", "Detected integrations"),
            ("Privacy", "privacy", "Privacy posture"),
            ("Skip — return to setup", "skip", ""),
        ],
        default_index=9,
    )


def print_runtime_strategy_guidance() -> None:
    print_box(
        "Runtime strategy",
        [
            "AethOS routes work to the best available reasoning engine.",
            "Local-first — privacy on your machine (Ollama).",
            "Cloud-first — powerful APIs when keys are configured.",
            "Hybrid — intelligent routing with calm fallback.",
            "Configure later — operational bootstrap first.",
        ],
    )


SETUP_GLOBAL_COMMANDS = (
    "help",
    "why",
    "skip",
    "back",
    "resume",
    "status",
    "recommended",
    "current",
    "repair",
    "quit",
)


def print_global_setup_commands() -> None:
    print_info("Commands: " + " · ".join(SETUP_GLOBAL_COMMANDS))


def print_setup_help() -> None:
    print_box(
        "Setup help",
        [
            "why — explain this step",
            "skip — defer (configure later)",
            "back — previous step when available",
            "status — show saved progress",
            "recommended — accept recommended defaults",
            "current — show current configuration",
            "repair — run setup repair",
            "quit — exit safely (progress saved)",
        ],
    )


def handle_setup_global_command(cmd: str) -> bool:
    """Return True if handled (caller should re-prompt)."""
    c = (cmd or "").strip().lower()
    if c == "help":
        print_setup_help()
        return True
    if c == "why":
        print_info("Each step configures how AethOS orchestrates workers, providers, and Mission Control.")
        return True
    if c in ("status", "current"):
        from app.services.setup.setup_continuity import build_setup_continuity

        cont = build_setup_continuity()
        print_info(cont["setup_continuity"].get("welcome_back_message", "No saved state"))
        return True
    if c == "recommended":
        print_info("Recommended: hybrid routing, seed Mission Control, calm operational defaults.")
        return True
    if c == "repair":
        try:
            from aethos_cli.setup_wizard import run_setup_wizard

            print_info("Starting setup repair…")
            run_setup_wizard(install_kind="repair")
        except Exception:
            print_info("Run: aethos setup repair")
        return True
    if c == "back":
        print_info("Back is limited in this wizard — use quit and `aethos setup resume`.")
        return True
    if c == "skip":
        print_info("Use skip at individual prompts where allowed.")
        return True
    return False


def calm_provider_validation_failed(provider: str) -> str:
    return (
        f"AethOS could not validate {provider} yet. "
        "You can retry now or continue setup and configure it later."
    )
