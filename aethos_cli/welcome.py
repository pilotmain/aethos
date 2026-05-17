# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Post-install success screen (Phase 32)."""

from __future__ import annotations

import sys
from pathlib import Path

from aethos_cli.ui import Colors, supports_color


def print_welcome_screen(
    *,
    install_dir: Path,
    workspace: Path,
    llm_summary: str,
    feature_labels: list[str],
    api_base: str,
    configuration_only: bool = False,
) -> None:
    """Framed completion message with honest next steps."""
    green = Colors.GREEN if supports_color() else ""
    cyan = Colors.CYAN if supports_color() else ""
    reset = Colors.RESET if supports_color() else ""
    feat = ", ".join(feature_labels) if feature_labels else "(defaults)"

    headline = "Configuration complete" if configuration_only else "AethOS installed successfully"
    banner = f"""{green}
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ✅ {headline:<68}║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝{reset}
"""
    print(banner, file=sys.stdout)
    print(f"   📍 Installation:  {install_dir}")
    print(f"   🤖 LLM:           {llm_summary}")
    print(f"   🔧 Features:      {feat}")
    print(f"   📊 Workspace:    {workspace}")
    if configuration_only:
        print("\n   ℹ️  Configuration saved. AethOS is not running until you start services.")
    print(f"\n   🚀 Quick start:")
    print("      aethos start                          # Start API + Mission Control (recommended)")
    print("      aethos runtime launch                 # Same as aethos start")
    print("      python -m aethos_cli serve            # API only (default :8010)")
    print("      python -m aethos_cli status           # Health checks")
    print("\n   🌐 After services start, open API docs at:")
    print(f"      {api_base.rstrip('/')}/docs")
    print("\n   🖥️  Full stack + Next.js Mission Control:")
    print("      docs/ENTERPRISE_SETUP.md — enterprise setup and launch")
    print("\n   📱 Mobile app: point API_BASE_URL at your machine (LAN IP + port).")
    print(f"\n{cyan}   Docs: docs/ENTERPRISE_SETUP.md{reset}\n")


__all__ = ["print_welcome_screen"]
