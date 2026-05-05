#!/usr/bin/env python3
"""
Phase 36 — Rewrite ``NEXA_*`` variable names to ``AETHOS_*`` in a ``.env`` file.

Creates ``.env.nexa_backup`` before writing. Comments and values are preserved.
Run ``python scripts/migrate_env_aethos.py --dry-run`` first.

Legacy processes still read ``NEXA_*`` via :func:`app.core.aethos_env.apply_aethos_env_aliases`
until you fully adopt ``AETHOS_*``.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

_LINE = re.compile(r"^(\s*)(NEXA_[A-Za-z0-9_]*)(\s*=\s*)(.*)(\r?\n)?$")


def migrate_line(line: str) -> str:
    m = _LINE.match(line)
    if not m:
        return line
    indent, key, eq, val, nl = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5) or ""
    return f"{indent}{key.replace('NEXA_', 'AETHOS_', 1)}{eq}{val}{nl}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Rewrite NEXA_* keys to AETHOS_* in .env")
    ap.add_argument("--env-file", type=Path, default=Path.cwd() / ".env")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    path: Path = args.env_file
    if not path.is_file():
        raise SystemExit(f"Not found: {path}")

    text = path.read_text(encoding="utf-8")
    out_lines = [migrate_line(line) for line in text.splitlines(keepends=True)]
    out = "".join(out_lines)
    if args.dry_run:
        print(out)
        return

    bak = path.with_name(path.name + ".nexa_backup")
    bak.write_text(text, encoding="utf-8")
    path.write_text(out, encoding="utf-8")
    print(f"Updated {path} (backup {bak})")


if __name__ == "__main__":
    main()
