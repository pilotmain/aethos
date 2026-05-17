# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Argparse helpers — deduplicated subparser registration."""

from __future__ import annotations

import argparse
from typing import Any


def add_runtime_parser_once(
    rt_sub: argparse._SubParsersAction,
    registry: set[str],
    name: str,
    **kwargs: Any,
) -> argparse.ArgumentParser:
    """Register a runtime subcommand at most once (prevents argparse conflicts)."""
    if name in registry:
        existing = rt_sub.choices.get(name) if rt_sub.choices else None
        if existing is not None:
            return existing
        raise argparse.ArgumentError(
            None,
            f"runtime_cmd: duplicate subparser registration for {name!r}",
        )
    registry.add(name)
    return rt_sub.add_parser(name, **kwargs)


def find_duplicate_runtime_parser_names(source: str) -> list[str]:
    """Static audit: duplicate rt_sub.add_parser names in source text."""
    import re
    from collections import Counter

    names = re.findall(r"rt_sub\.add_parser\(\s*[\"']([^\"']+)[\"']", source)
    return [n for n, c in Counter(names).items() if c > 1]
