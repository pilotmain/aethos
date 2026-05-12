#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Emit a single 'set -a' + safe 'export KEY=...' block for the repo's .env.
Values come from python-dotenv (one line = one var; spaces in unquoted values stay in the value).
Skips TERM/TERMCAP. Used by _host_dev_executor_impl.sh for sourcing without running stray commands
(e.g. bash interpreting 'Reset' as a command after a broken APP_NAME= line).
"""
from __future__ import annotations

import re
from pathlib import Path

_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SKIP = {"TERM", "TERMCAP", "term", "termcap"}


def _sh_quote(val: str) -> str:
  return "'" + val.replace("'", "'\"'\"'") + "'"


def _load_pairs_from_file(envf: Path) -> dict[str, str]:
  try:
    from dotenv import dotenv_values
  except ImportError:
    out: dict[str, str] = {}
    for raw in envf.read_text(encoding="utf-8", errors="replace").splitlines():
      line = raw.split("#", 1)[0].rstrip()
      s = line.strip()
      if not s:
        continue
      if s.lstrip().startswith("export "):
        s = s.lstrip()[7:].lstrip()
      if "=" not in s:
        continue
      k, v = s.split("=", 1)
      k = k.strip()
      v = v.strip()
      if not k or not _KEY.match(k):
        continue
      if k in _SKIP or k.upper() in _SKIP or k.lower() in _SKIP:
        continue
      out[k] = v
    return out
  d = dotenv_values(str(envf)) or {}
  return {
    k: (v or "")
    for k, v in d.items()
    if k and _KEY.match(k) and k not in _SKIP and k.upper() not in _SKIP
  }


def main() -> int:
  root = Path(__file__).resolve().parent.parent
  envf = root / ".env"
  if not envf.is_file():
    return 0
  pairs = _load_pairs_from_file(envf)
  if not pairs:
    return 0
  print("set -a", flush=True)
  for k, v in pairs.items():
    if not k or not _KEY.match(k):
      continue
    if k in _SKIP or k.lower() in _SKIP:
      continue
    if k in ("term", "termcap"):
      continue
    print(f"export {k}={_sh_quote(v)}", flush=True)
  print("set +a", flush=True)
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
