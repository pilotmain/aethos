"""
Security scanner configuration: ignore rules, test heuristics, optional .secretsignore.
"""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Sequence

# Optional local patterns (one glob per line, # comments).
_SECRETSIGNORE_NAME = ".secretsignore"


class SecurityScannerConfig:
    """Paths and patterns excluded from heuristic secret scanning."""

    IGNORE_DIRS: frozenset[str] = frozenset(
        {
            ".git",
            ".venv",
            "venv",
            "node_modules",
            "__pycache__",
            "dist",
            "build",
            ".pytest_cache",
            ".mypy_cache",
            "site-packages",
            ".next",
            "coverage",
            ".turbo",
            "htmlcov",
        }
    )

    IGNORE_FILES: tuple[str, ...] = (
        "*.lock",
        "*.min.js",
        "*.min.css",
        "*.pyc",
        "*.pyo",
        "*.so",
        "*.dll",
        "*.exe",
        "*.png",
        "*.jpg",
        "*.jpeg",
        "*.gif",
        "*.webp",
        "*.ico",
        "*.woff",
        "*.woff2",
        "*.ttf",
        "*.parquet",
        "*.zip",
    )

    # Relative POSIX paths / globs from repo root.
    IGNORE_PATHS: tuple[str, ...] = (
        "tests/",
        "test/",
        "migrations/",
        "scripts/",
        "examples/",
        "docs/",
        "fixtures/",
        "vendor/",
        "**/test_*.py",
        "**/*_test.py",
        "**/conftest.py",
    )

    TEST_INDICATORS: tuple[str, ...] = (
        "test_",
        "_test",
        "fixture",
        "mock",
        "fake",
        "example",
        "demo",
        "sample",
        "/tests/",
        "\\tests\\",
        "/test/",
        "\\test\\",
    )

    @classmethod
    def load_secretsignore(cls, root: Path) -> list[str]:
        p = root / _SECRETSIGNORE_NAME
        if not p.is_file():
            return []
        out: list[str] = []
        try:
            raw = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []
        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(line)
        return out

    @classmethod
    def should_ignore_file(
        cls,
        file_path: str,
        root: Path,
        *,
        extra_patterns: Sequence[str] | None = None,
    ) -> bool:
        """Return True if path should be skipped (vendor, generated, docs, tests, etc.)."""
        try:
            root_r = root.resolve()
            full = Path(file_path).resolve()
            rel = full.relative_to(root_r)
        except ValueError:
            return False

        rel_s = rel.as_posix()
        name = rel.name

        for part in rel.parts:
            if part in cls.IGNORE_DIRS:
                return True

        for pat in cls.IGNORE_FILES:
            if fnmatch.fnmatch(name, pat):
                return True

        for pat in cls.IGNORE_PATHS:
            if cls._matches_ignore_pattern(rel_s, name, pat):
                return True

        if extra_patterns:
            for pat in extra_patterns:
                if cls._matches_ignore_pattern(rel_s, name, pat):
                    return True

        return False

    @staticmethod
    def _matches_ignore_pattern(rel_s: str, name: str, pat: str) -> bool:
        if pat.endswith("/"):
            prefix = pat.rstrip("/")
            return rel_s == prefix or rel_s.startswith(prefix + "/")
        if "**/" in pat:
            suffix = pat.split("**/")[-1]
            if fnmatch.fnmatch(rel_s, pat):
                return True
            if suffix and fnmatch.fnmatch(name, suffix):
                return True
            rest = pat.replace("**/", "")
            if fnmatch.fnmatch(rel_s, rest):
                return True
        if "*" in pat or "?" in pat:
            return fnmatch.fnmatch(rel_s, pat) or fnmatch.fnmatch(name, pat)
        return rel_s == pat or rel_s.startswith(pat + "/")

    @classmethod
    def is_likely_test_file(cls, file_path: str) -> bool:
        path_l = str(file_path).lower()
        if path_l.endswith("conftest.py"):
            return True
        for indicator in cls.TEST_INDICATORS:
            if indicator in path_l:
                return True
        return False


__all__ = ["SecurityScannerConfig"]
