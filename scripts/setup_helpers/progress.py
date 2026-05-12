# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Simple terminal progress bar."""

from __future__ import annotations

import sys
import time
from typing import Any


class ProgressBar:
    """ASCII progress bar with optional indeterminate animation."""

    def __init__(
        self,
        total: int,
        prefix: str = "",
        suffix: str = "",
        length: int = 40,
    ) -> None:
        self.total = max(total, 1)
        self.prefix = prefix
        self.suffix = suffix
        self.length = length
        self.current = 0

    def update(self, current: int | None = None) -> None:
        from .colors import Colors

        if current is not None:
            self.current = min(max(current, 0), self.total)
        else:
            self.current = min(self.current + 1, self.total)

        pct = 100.0 * (self.current / self.total)
        filled = int(self.length * self.current // self.total)
        bar = f"{Colors.GREEN}{'█' * filled}{Colors.RESET}{'░' * (self.length - filled)}"
        sys.stdout.write(f"\r{self.prefix} |{bar}| {pct:.1f}% {self.suffix}")
        sys.stdout.flush()
        if self.current >= self.total:
            sys.stdout.write("\n")
            sys.stdout.flush()

    def animate_while(self, fn: Any, *, steps: int = 20, interval: float = 0.12) -> Any:
        """Run ``fn`` while advancing the bar until ``fn`` completes (blocking)."""
        self.current = 0
        start = time.monotonic()
        result_holder: list[Any] = []
        exc_holder: list[BaseException] = []

        def _run() -> None:
            try:
                result_holder.append(fn())
            except BaseException as e:  # noqa: BLE001 — propagate after animation
                exc_holder.append(e)

        import threading

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        i = 0
        while t.is_alive():
            i = (i + 1) % steps
            self.update(i)
            time.sleep(interval)
        t.join()
        self.update(self.total)
        if exc_holder:
            raise exc_holder[0]
        return result_holder[0] if result_holder else None

    def __enter__(self) -> ProgressBar:
        return self

    def __exit__(self, *_args: object) -> None:
        if self.current < self.total:
            self.update(self.total)
