# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Phase 16 — AST scan: no direct ``openai`` / ``anthropic`` imports outside ``app/services/providers``."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
PROVIDERS = APP / "services" / "providers"
FORBIDDEN_ROOTS = frozenset({"openai", "anthropic"})


def _root_name(module: str | None) -> str | None:
    if not module:
        return None
    return module.split(".", 1)[0]


def _walk_py_files(base: Path) -> list[Path]:
    out: list[Path] = []
    for path in base.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        try:
            path.resolve().relative_to(PROVIDERS.resolve())
        except ValueError:
            out.append(path)
        else:
            continue
    return out


def test_no_direct_vendor_imports_outside_providers() -> None:
    for path in _walk_py_files(APP):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = _root_name(alias.name)
                    assert root not in FORBIDDEN_ROOTS, f"{path.relative_to(ROOT)} imports {alias.name}"
            if isinstance(node, ast.ImportFrom):
                root = _root_name(node.module)
                assert root not in FORBIDDEN_ROOTS, f"{path.relative_to(ROOT)} imports from {node.module}"
