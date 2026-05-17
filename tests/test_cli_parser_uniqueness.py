# SPDX-License-Identifier: Apache-2.0

"""CLI must build argparse without duplicate runtime subparser crashes."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from aethos_cli.cli_parser_helpers import find_duplicate_runtime_parser_names


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def test_runtime_parser_names_unique_in_source() -> None:
    src = (_repo_root() / "aethos_cli" / "__main__.py").read_text(encoding="utf-8")
    legacy = find_duplicate_runtime_parser_names(src)
    assert legacy == [], f"duplicate rt_sub.add_parser names: {legacy}"
    names = re.findall(
        r"add_runtime_parser_once\(rt_sub, _runtime_parser_names,\s*[\"']([^\"']+)[\"']",
        src,
    )
    from collections import Counter

    dup = [n for n, c in Counter(names).items() if c > 1]
    assert dup == [], f"duplicate add_runtime_parser_once names: {dup}"


def test_cli_help_commands_do_not_crash() -> None:
    py = sys.executable
    root = _repo_root()
    cases = [
        ["--help"],
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
