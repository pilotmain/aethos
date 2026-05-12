# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

from __future__ import annotations

from app.services.dev_tools.registry import list_dev_tools


def format_dev_tools() -> str:
    lines = ["Nexa Dev tools:\n"]

    for tool in list_dev_tools():
        available = "available" if tool.is_available() else "not detected"  # type: ignore[union-attr]
        modes = ", ".join(tool.supported_modes)  # type: ignore[union-attr]
        lines.append(
            f"— `{tool.key}` — {tool.display_name} ({available}; {modes})"  # type: ignore[union-attr]
        )

    lines.append("\nSet per project:")
    lines.append("/project set-tool nexa vscode")
    lines.append("/project set-mode nexa autonomous_cli")

    return "\n".join(lines)
