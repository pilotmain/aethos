"""Pick an allowlisted test command for the repo layout + parse failures (Phase 25)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.services.dev_runtime.executor import run_dev_command


def pick_test_command(repo_root: Path) -> str:
    """Prefer pytest for Python repos, else npm test when package.json has a test script."""
    pkg = repo_root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            scripts = data.get("scripts") or {}
            if isinstance(scripts, dict) and scripts.get("test"):
                return "npm test"
        except (OSError, json.JSONDecodeError):
            pass
    if (
        (repo_root / "pytest.ini").is_file()
        or (repo_root / "pyproject.toml").is_file()
        or (repo_root / "tests").is_dir()
    ):
        return "python -m pytest"
    return "python -m pytest"


_RE_FAILED_SIGNAL = re.compile(r"\b(?:FAILED|ERROR|AssertionError|SyntaxError)\b", re.IGNORECASE)
_RE_PATH_HINT = re.compile(r"([\w/.+-]+\.(?:py|ts|tsx|js|jsx))(?::\d+)?")


def parse_test_failures(output: str) -> dict[str, Any]:
    """
    Best-effort extraction of pytest/npm/Jest failure signals.

    Returns summary text, probable files, error lines, and a coarse failure count.
    """
    raw = output or ""
    lines = raw.splitlines()
    errors: list[str] = []
    for line in lines:
        if _RE_FAILED_SIGNAL.search(line) or " FAIL " in line or line.strip().startswith("FAIL "):
            errors.append(line.strip()[:800])
        elif "● " in line or "Expected:" in line:
            errors.append(line.strip()[:800])

    files: list[str] = []
    for m in _RE_PATH_HINT.finditer(raw):
        files.append(m.group(1))
    seen_f = sorted(set(files))[:40]

    fail_ct = len(errors)
    if not fail_ct:
        m = re.search(r"(\d+)\s+failed", raw, re.IGNORECASE)
        if m:
            fail_ct = int(m.group(1))

    summary = "; ".join(errors[:8]) if errors else (raw.strip()[-2500:] if raw.strip() else "no output")
    if len(summary) > 2000:
        summary = summary[:1997] + "…"
    fc = fail_ct if fail_ct else len(errors)
    return {
        "summary": summary,
        "files": seen_f,
        "errors": errors[:40],
        "failure_count": min(fc, 999),
    }


def run_repo_tests(repo_root: Path | str) -> dict[str, Any]:
    """Run allowlisted tests for ``repo_root`` and parse stdout/stderr."""
    root = Path(repo_root)
    cmd = pick_test_command(root)
    te = run_dev_command(root, cmd)
    merged_out = ((te.get("stdout") or "") + "\n" + (te.get("stderr") or "")).strip()
    parsed = parse_test_failures(merged_out)
    ok = bool(te.get("ok"))
    return {
        "ok": ok,
        "command": cmd,
        "summary": parsed["summary"] if not ok else "tests passed",
        "parsed": parsed,
        "command_result": te,
        "stdout_preview": (te.get("stdout") or "")[-12000:],
        "stderr_preview": (te.get("stderr") or "")[-8000:],
    }


__all__ = ["pick_test_command", "parse_test_failures", "run_repo_tests"]
