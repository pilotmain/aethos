"""Phase 16 — plugins register tools only; no DB or provider imports."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "app" / "plugins"

FORBIDDEN_FROM_ROOTS = frozenset(
    {
        "openai",
        "anthropic",
        "app.services.providers",
        "sqlalchemy",
        "app.core.db",
    },
)


def _root_from_import_from(module: str | None) -> str | None:
    if not module:
        return None
    parts = module.split(".")
    if len(parts) >= 3 and parts[0] == "app" and parts[1] == "services" and parts[2] == "providers":
        return "app.services.providers"
    if len(parts) >= 3 and parts[0] == "app" and parts[1] == "core" and parts[2] == "db":
        return "app.core.db"
    return parts[0] if parts else None


def test_plugins_do_not_import_db_or_providers() -> None:
    for path in sorted(PLUGINS.glob("*.py")):
        if path.name.startswith("__"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    assert root not in ("openai", "anthropic", "sqlalchemy"), f"{path.name}: {alias.name}"
                    assert not alias.name.startswith(
                        ("app.services.providers", "app.core.db"),
                    ), f"{path.name}: {alias.name}"
            if isinstance(node, ast.ImportFrom):
                mod = _root_from_import_from(node.module)
                if mod in FORBIDDEN_FROM_ROOTS:
                    raise AssertionError(f"{path.name}: forbidden import from {node.module}")
