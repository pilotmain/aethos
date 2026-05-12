#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Copy an explicit allowlist of paths into the sibling ``aethos-core`` clone and optionally commit/push."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Paths intended for the public mirror (missing sources are skipped with a warning).
PUBLIC_PATHS: tuple[str, ...] = (
    "aethos_core/",
    "app/services/response_formatter.py",
    "app/services/file_ops.py",
    "app/services/command_executor.py",
    "tests/test_response_formatter.py",
    "tests/test_command_execution.py",
    "README.md",
    "LICENSE",
)


def _run_git(args: list[str], *, cwd: Path, capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=capture,
    )


def _has_staged_changes(repo: Path) -> bool:
    r = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=repo)
    return r.returncode != 0


def _sync_one(repo_root: Path, public_repo: Path, rel: str, *, dry_run: bool) -> bool:
    src = repo_root / rel
    dst = public_repo / rel

    if not src.exists():
        print(f"  ⚠️  skip (missing in main repo): {rel}")
        return False

    if dry_run:
        print(f"  · would sync: {rel}")
        return True

    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dst, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst)
    print(f"  ✓ {rel}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export allowlisted public paths to ../aethos-core")
    parser.add_argument(
        "--public-repo",
        type=Path,
        default=None,
        help="Path to aethos-core checkout (default: sibling ../aethos-core)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions only; do not copy or touch git in the public repo",
    )
    parser.add_argument(
        "--no-push",
        action="store_true",
        help="Commit locally but do not push (for CI: push in a later step)",
    )
    parser.add_argument(
        "--skip-pull",
        action="store_true",
        help="Do not git pull in the public repo before copying",
    )
    ns = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    public_repo = (ns.public_repo or (repo_root.parent / "aethos-core")).resolve()

    if ns.dry_run:
        print("📋 Dry run — allowlisted paths in main repo:")
        for path in PUBLIC_PATHS:
            src = repo_root / path
            label = "✓" if src.exists() else "⚠️  missing"
            print(f"  {label} {path}")
        print("(requires a ../aethos-core clone for copy/commit/push)")
        return 0

    if not public_repo.is_dir():
        print(f"❌ Public repo not found at {public_repo}")
        print("Clone it first, e.g.: git clone git@github.com:pilotmain/aethos-core.git ../aethos-core")
        return 1

    if not ns.skip_pull:
        print("📥 Pulling latest in public repo…")
        pr = _run_git(["pull", "--ff-only"], cwd=public_repo, capture=True)
        if pr.returncode != 0:
            print(pr.stderr or pr.stdout or "(no output)")
            print("❌ git pull failed in public repo")
            return 1

    print("📋 Copying public files…")
    for path in PUBLIC_PATHS:
        _sync_one(repo_root, public_repo, path, dry_run=bool(ns.dry_run))

    if ns.dry_run:
        print("✅ Dry run complete")
        return 0

    _run_git(["add", "-A"], cwd=public_repo)
    if not _has_staged_changes(public_repo):
        print("✅ No changes to export")
        return 0

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    msg = f"Auto-export from main repo — {ts}"
    c = _run_git(["commit", "-m", msg], cwd=public_repo, capture=True)
    if c.returncode != 0:
        print(c.stderr or c.stdout or "")
        print("❌ git commit failed")
        return 1

    if ns.no_push:
        print("📦 Committed locally (--no-push); not pushing")
        return 0

    print("📤 Pushing…")
    p = _run_git(["push"], cwd=public_repo, capture=True)
    if p.returncode != 0:
        print(p.stderr or p.stdout or "")
        print("❌ git push failed")
        return 1
    print("✅ Successfully exported to public repo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
