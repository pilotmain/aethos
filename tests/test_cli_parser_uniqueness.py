# SPDX-License-Identifier: Apache-2.0

"""CLI must build argparse without duplicate subparser crashes."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from aethos_cli.cli_parser_helpers import (
    add_parser_once,
    find_duplicate_runtime_parser_names,
    find_duplicate_top_level_parser_names,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_runtime_parser_names_unique_in_source() -> None:
    src = (_repo_root() / "aethos_cli" / "__main__.py").read_text(encoding="utf-8")
    legacy = find_duplicate_runtime_parser_names(src)
    assert legacy == [], f"duplicate runtime parser names: {legacy}"


def test_top_level_parser_names_unique_in_source() -> None:
    src = (_repo_root() / "aethos_cli" / "__main__.py").read_text(encoding="utf-8")
    assert re.search(r"(?<![.\w])sub\.add_parser\(", src) is None, "use _cmd() for top-level parsers"
    dup = find_duplicate_top_level_parser_names(src)
    assert dup == [], f"duplicate top-level parser names: {dup}"


def test_add_parser_once_idempotent() -> None:
    import argparse

    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd")
    names: set[str] = set()
    p1 = add_parser_once(sp, names, "restart", help="first")
    p2 = add_parser_once(sp, names, "restart", help="second")
    assert p1 is p2
    assert names == {"restart"}


def test_cli_help_commands_do_not_crash() -> None:
    py = sys.executable
    root = _repo_root()
    cases = [
        ["--help"],
        ["restart", "--help"],
        ["start", "--help"],
        ["runtime", "--help"],
        ["doctor", "--help"],
        ["setup", "resume", "--help"],
        ["repair", "--help"],
    ]
    for argv in cases:
        proc = subprocess.run(
            [py, "-m", "aethos_cli", *argv],
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert proc.returncode == 0, (
            f"aethos {' '.join(argv)} failed exit={proc.returncode}\n"
            f"stderr={proc.stderr[:2000]}\nstdout={proc.stdout[:500]}"
        )
        combined = (proc.stderr or "") + (proc.stdout or "")
        assert "conflicting subparser" not in combined.lower()
        assert "ArgumentError" not in combined


def test_setup_entrypoint_imports_without_argparse_crash() -> None:
    """Simulates curl|bash path: aethos setup must not crash at parser build."""
    proc = subprocess.run(
        [sys.executable, "-m", "aethos_cli", "setup", "--help"],
        cwd=str(_repo_root()),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0
    assert "conflicting subparser" not in (proc.stderr + proc.stdout).lower()


def test_build_runtime_subparsers_via_main_import() -> None:
    """Importing main and building argparse must not raise."""
    import argparse

    from aethos_cli.cli_parser_helpers import add_runtime_parser_once

    p = argparse.ArgumentParser()
    sp = p.add_subparsers(dest="cmd")
    rt = sp.add_parser("runtime")
    rt_sub = rt.add_subparsers(dest="runtime_cmd", required=True)
    names: set[str] = set()
    p1 = add_runtime_parser_once(rt_sub, names, "responsiveness", help="metrics")
    add_runtime_parser_once(rt_sub, names, "responsiveness-guarantees", help="guarantees")
    p2 = add_runtime_parser_once(rt_sub, names, "responsiveness", help="dup")
    assert p1 is p2
    assert names == {"responsiveness", "responsiveness-guarantees"}
