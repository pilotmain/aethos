# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Platform detection for macOS, Windows, Linux (Phase 25 native setup UX).
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def detect() -> dict[str, Any]:
    """Return OS, architecture, CPU hint, and paths."""
    system = platform.system().lower()
    arch = (platform.machine() or "").lower()
    info: dict[str, Any] = {
        "os": system,
        "arch": arch,
        "python_version": sys.version.split()[0],
        "is_mac": system == "darwin",
        "is_windows": system.startswith("win"),
        "is_linux": system == "linux",
        "is_arm64": arch in ("arm64", "aarch64"),
        "is_x86_64": arch in ("x86_64", "amd64"),
        "home_dir": str(Path.home()),
        "cpu": "",
    }

    if system == "darwin":
        try:
            r = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                info["cpu"] = r.stdout.strip()
            elif info["is_arm64"]:
                info["cpu"] = "Apple Silicon"
            else:
                info["cpu"] = "Intel Mac"
        except (OSError, subprocess.TimeoutExpired):
            info["cpu"] = "macOS"
    elif system == "linux":
        try:
            proc_cpu = Path("/proc/cpuinfo")
            if proc_cpu.is_file():
                for line in proc_cpu.read_text(encoding="utf-8", errors="ignore").splitlines():
                    if "model name" in line.lower():
                        info["cpu"] = line.split(":", 1)[1].strip()
                        break
        except OSError:
            pass
        if not info["cpu"]:
            info["cpu"] = arch or "Linux"
    elif system.startswith("win"):
        info["cpu"] = os.environ.get("PROCESSOR_IDENTIFIER", "") or arch or "Windows"

    return info


def human_os_line(info: dict[str, Any]) -> str:
    """One-line human summary for banners."""
    if info.get("is_mac"):
        chip = "Apple Silicon" if info.get("is_arm64") else "Intel"
        ver = platform.mac_ver()[0] or ""
        tail = f" {ver}" if ver else ""
        return f"macOS{tail} ({chip})"
    if info.get("is_windows"):
        return f"Windows ({info.get('arch', '')})"
    if info.get("is_linux"):
        return f"Linux ({info.get('arch', '')})"
    return f"{info.get('os', '?')} ({info.get('arch', '')})"


def get_install_hint() -> str:
    """Platform-specific install hints (placeholders until distro packages exist)."""
    info = detect()
    if info.get("is_mac"):
        return "brew install python@3.12  # then re-run this installer"
    if info.get("is_windows"):
        return "Install Python 3.10+ from https://www.python.org/downloads/windows/"
    return "curl -fsSL https://raw.githubusercontent.com/pilotmain/aethos/main/install.sh | bash"


def ollama_install_hint() -> str:
    """Short hint for installing Ollama when missing."""
    info = detect()
    if info.get("is_mac"):
        return "brew install ollama"
    if info.get("is_linux"):
        return "curl -fsSL https://ollama.ai/install.sh | sh"
    if info.get("is_windows"):
        return "Install from https://ollama.ai/download"
    return "https://ollama.ai"


def detect_optional_tool(name: str) -> str | None:
    """Return version line if ``name --version`` works (e.g. ``git``, ``node``)."""
    exe = shutil.which(name)
    if not exe:
        return None
    try:
        r = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=8)
        if r.returncode != 0:
            return None
        line = (r.stdout or r.stderr or "").strip().splitlines()[0]
        return line[:80] if line else name
    except (OSError, subprocess.TimeoutExpired):
        return None


__all__ = ["detect", "detect_optional_tool", "get_install_hint", "human_os_line", "ollama_install_hint"]
