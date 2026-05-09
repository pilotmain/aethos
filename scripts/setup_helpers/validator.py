"""Lightweight environment checks for the setup wizard."""

from __future__ import annotations

import shutil
import socket
import sys
from typing import Tuple


class Validator:
    """Configuration and system validation helpers."""

    @staticmethod
    def check_port(port: int) -> Tuple[bool, str]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", int(port)))
                return True, f"Port {port} is available"
            except OSError:
                return False, f"Port {port} is already in use"

    @staticmethod
    def check_common_api_ports() -> Tuple[bool, str]:
        """Prefer 8010; accept either 8000 or 8010 if one is free."""
        ok800, m800 = Validator.check_port(8000)
        ok801, m801 = Validator.check_port(8010)
        if ok801:
            return True, m801
        if ok800:
            return True, m800
        return False, f"{m800}; {m801}"

    @staticmethod
    def check_python_version(min_major: int = 3, min_minor: int = 9) -> Tuple[bool, str]:
        v = sys.version_info
        if v.major > min_major or (v.major == min_major and v.minor >= min_minor):
            return True, f"Python {v.major}.{v.minor}.{v.micro}"
        return False, f"Python {min_major}.{min_minor}+ required (found {v.major}.{v.minor})"

    @staticmethod
    def check_disk_space(path: str = ".", min_gb: float = 1.0) -> Tuple[bool, str]:
        free = shutil.disk_usage(path).free
        free_gb = free / (1024**3)
        if free_gb >= min_gb:
            return True, f"{free_gb:.1f} GB available"
        return False, f"Only {free_gb:.1f} GB free (recommend {min_gb:.0f}+ GB)"
