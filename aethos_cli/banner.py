"""AethOS CLI / terminal brand banner (ASCII)."""

from __future__ import annotations

import os
import sys

# Primary wordmark + tagline — fits standard 120-column terminals.
BANNER = r"""
╔═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                                                                                                                   ║
║                         █████╗ ███████╗████████╗██╗  ██╗ ██████╗ ███████╗                                        ║
║                        ██╔══██╗██╔════╝╚══██╔══╝██║  ██║██╔═══██╗██╔════╝                                        ║
║                        ███████║█████╗     ██║   ███████║██║   ██║███████╗                                        ║
║                        ██╔══██║██╔══╝     ██║   ██╔══██║██║   ██║╚════██║                                        ║
║                        ██║  ██║███████╗   ██║   ██║  ██║╚██████╔╝███████║                                        ║
║                        ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝                                        ║
║                                                                                                                   ║
║   ┌─────────────────────────────────────────────────────────────────────────────────────────────────────────┐     ║
║   │                                                                                                         │     ║
║   │                    "The invisible layer that connects all autonomous agents"                            │     ║
║   │                                                                                                         │     ║
║   └─────────────────────────────────────────────────────────────────────────────────────────────────────────┘     ║
║                                                                                                                   ║
╚═══════════════════════════════════════════════════════════════════════════════════════════════════════════════════╝
""".strip(
    "\n"
)


def should_show_banner() -> bool:
    if os.environ.get("AETHOS_CLI_NO_BANNER") or os.environ.get("NEXA_CLI_NO_BANNER"):
        return False
    if not sys.stderr.isatty():
        return False
    return True


def maybe_print_sponsor_hint(*, stream=sys.stderr) -> None:
    """Optional one-line GitHub Sponsors hint (set ``AETHOS_SPONSOR_HINT=1``)."""
    if (os.environ.get("AETHOS_SPONSOR_HINT") or "").strip().lower() not in ("1", "true", "yes"):
        return
    if not stream.isatty():
        return
    print("Support AethOS on GitHub Sponsors: https://github.com/sponsors/pilotmain", file=stream)


def print_banner(*, stream=sys.stderr) -> None:
    """Print banner to stderr so JSON stdout pipelines stay clean."""
    print(BANNER, file=stream)
