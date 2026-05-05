"""Post-install success screen (Phase 32)."""

from __future__ import annotations

import sys
from pathlib import Path

from nexa_cli.ui import Colors, supports_color


def print_welcome_screen(
    *,
    install_dir: Path,
    workspace: Path,
    llm_summary: str,
    feature_labels: list[str],
    api_base: str,
) -> None:
    """Large framed success message with quick start commands."""
    green = Colors.GREEN if supports_color() else ""
    cyan = Colors.CYAN if supports_color() else ""
    reset = Colors.RESET if supports_color() else ""
    feat = ", ".join(feature_labels) if feature_labels else "(defaults)"

    banner = f"""{green}
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ✅ Nexa installed successfully!                                           ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝{reset}
"""
    print(banner, file=sys.stdout)
    print(f"   📍 Installation:  {install_dir}")
    print(f"   🤖 LLM:           {llm_summary}")
    print(f"   🔧 Features:      {feat}")
    print(f"   📊 Workspace:    {workspace}")
    print(f"\n   🚀 Quick start:")
    print("      python -m nexa_cli serve          # API (default http://0.0.0.0:8010)")
    print("      python -m nexa_cli status         # Health checks")
    print("\n   🌐 After `serve`, open API docs at:")
    print(f"      {api_base.rstrip('/')}/docs")
    print("\n   🖥️  Full stack + Next.js Mission Control:")
    print("      ./scripts/nexa_next_local_all.sh start")
    print("\n   📱 Mobile app: point API_BASE_URL at your machine (LAN IP + port).")
    print(f"\n{cyan}   Docs: docs/NATIVE_SETUP.md{reset}\n")


__all__ = ["print_welcome_screen"]
