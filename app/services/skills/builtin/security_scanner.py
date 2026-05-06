"""
Static security heuristics over a repo tree (secrets-ish patterns, unsafe calls).

``@qa_agent`` uses the enhanced pipeline in ``app.services.qa_agent.security_review`` (ignores, gitleaks/trufflehog/pip-audit when available). This module remains a lightweight heuristic helper.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_SKIP_DIRS = frozenset(
    {".venv", "venv", "node_modules", "__pycache__", ".git", "dist", "build", ".next", "coverage"}
)

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"(api[_-]?key|apikey)\s*=\s*['\"]([^'\"]{8,})['\"]", re.I), "Possible hardcoded API key assignment", "HIGH"),
    (re.compile(r"(token|secret|password)\s*=\s*['\"]([^'\"]{12,})['\"]", re.I), "Possible hardcoded credential assignment", "HIGH"),
    (re.compile(r"-----BEGIN (RSA |OPENSSH )?PRIVATE KEY-----"), "Private key material", "HIGH"),
    (re.compile(r"\bghp_[a-zA-Z0-9]{30,}\b"), "GitHub PAT-shaped token", "HIGH"),
    (re.compile(r"\bsk-[a-zA-Z0-9]{40,}\b"), "API key-shaped token (sk-…)", "MEDIUM"),
]

_UNSAFE_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"\beval\s*\("), "eval() call", "HIGH"),
    (re.compile(r"\bexec\s*\("), "exec() call", "HIGH"),
    (re.compile(r"\bos\.system\s*\("), "os.system()", "MEDIUM"),
    (re.compile(r"\bsubprocess\.(?:call|run|Popen)\s*\("), "subprocess invocation (review args)", "MEDIUM"),
]

_TEXT_SUFFIXES = frozenset({".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml", ".yml", ".env", ".toml", ".md"})

_CODE_SUFFIXES = frozenset({".py", ".js", ".ts", ".tsx", ".jsx"})

_MAX_FILES = 8000


def _walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        yield dirpath, filenames


def scan_for_secrets(root_path: str | Path) -> list[dict[str, Any]]:
    root = Path(root_path).resolve()
    issues: list[dict[str, Any]] = []
    n = 0
    for dirpath, filenames in _walk(root):
        for name in filenames:
            if n >= _MAX_FILES:
                return issues
            suf = Path(name).suffix.lower()
            if suf not in _TEXT_SUFFIXES and name != ".env":
                continue
            fp = Path(dirpath) / name
            n += 1
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                for pat, desc, sev in _SECRET_PATTERNS:
                    if pat.search(line):
                        issues.append({"file": str(fp), "line": i, "issue": desc, "severity": sev})
                        break
    return issues


def scan_for_dependencies(root_path: str | Path) -> list[dict[str, Any]]:
    root = Path(root_path).resolve()
    issues: list[dict[str, Any]] = []
    req = root / "requirements.txt"
    if req.is_file():
        issues.append(
            {
                "file": str(req),
                "issue": "Use pip-audit or safety against requirements.txt for CVE coverage",
                "severity": "INFO",
            }
        )
    pkg = root / "package.json"
    if pkg.is_file():
        issues.append(
            {
                "file": str(pkg),
                "issue": "Run npm audit / pnpm audit for dependency vulnerabilities",
                "severity": "INFO",
            }
        )
    return issues


def scan_for_unsafe_patterns(root_path: str | Path) -> list[dict[str, Any]]:
    root = Path(root_path).resolve()
    issues: list[dict[str, Any]] = []
    n = 0
    for dirpath, filenames in _walk(root):
        for name in filenames:
            if n >= _MAX_FILES:
                return issues
            suf = Path(name).suffix.lower()
            if suf not in _CODE_SUFFIXES:
                continue
            fp = Path(dirpath) / name
            n += 1
            try:
                with fp.open(encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        for pat, desc, sev in _UNSAFE_PATTERNS:
                            if pat.search(line):
                                issues.append({"file": str(fp), "line": i, "issue": desc, "severity": sev})
                                break
            except OSError:
                continue
    return issues


def scan_security(root_path: str | Path) -> dict[str, Any]:
    """Run heuristic scans; results are advisory."""
    rp = str(Path(root_path).resolve())
    return {
        "root": rp,
        "secrets": scan_for_secrets(rp),
        "dependencies": scan_for_dependencies(rp),
        "unsafe_patterns": scan_for_unsafe_patterns(rp),
    }


__all__ = ["scan_for_secrets", "scan_for_dependencies", "scan_for_unsafe_patterns", "scan_security"]
