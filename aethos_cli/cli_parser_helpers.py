# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Argparse helpers — deduplicated subparser registration."""

from __future__ import annotations

import argparse
from collections import Counter
from typing import Any


def add_parser_once(
    sub: argparse._SubParsersAction,
    registry: set[str],
    name: str,
    **kwargs: Any,
) -> argparse.ArgumentParser:
    """Register a subcommand at most once (idempotent; prevents argparse conflicts)."""
    if name in registry:
        existing = sub.choices.get(name) if sub.choices else None
        if existing is not None:
            return existing
        raise argparse.ArgumentError(
            None,
            f"conflicting subparser: {name!r} (registered in registry but missing from choices)",
        )
    registry.add(name)
    return sub.add_parser(name, **kwargs)


def add_runtime_parser_once(
    rt_sub: argparse._SubParsersAction,
    registry: set[str],
    name: str,
    **kwargs: Any,
) -> argparse.ArgumentParser:
    """Register a runtime subcommand at most once (prevents argparse conflicts)."""
    return add_parser_once(rt_sub, registry, name, **kwargs)


def find_duplicate_subparser_names(source: str, *, pattern: str) -> list[str]:
    """Static audit: duplicate add_parser names for a given regex pattern."""
    import re

    names = re.findall(pattern, source)
    return [n for n, c in Counter(names).items() if c > 1]


def find_duplicate_runtime_parser_names(source: str) -> list[str]:
    """Static audit: duplicate rt_sub.add_parser names in source text."""
    legacy = find_duplicate_subparser_names(source, pattern=r"rt_sub\.add_parser\(\s*[\"']([^\"']+)[\"']")
    helper_dup = find_duplicate_subparser_names(
        source,
        pattern=r"add_runtime_parser_once\(rt_sub, _runtime_parser_names,\s*[\"']([^\"']+)[\"']",
    )
    return sorted(set(legacy + helper_dup))


def find_duplicate_top_level_parser_names(source: str) -> list[str]:
    """Static audit: duplicate top-level sub command names."""
    legacy = find_duplicate_subparser_names(source, pattern=r"(?:^|[^\w])sub\.add_parser\(\s*[\"']([^\"']+)[\"']")
    helper_dup = find_duplicate_subparser_names(
        source,
        pattern=r"_cmd\(\s*[\"']([^\"']+)[\"']",
    )
    return sorted(set(legacy + helper_dup))
