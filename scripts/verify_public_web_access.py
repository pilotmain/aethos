#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
Manual / CI helper: one-shot public URL read (Phase 1). Run from repo root with .env loaded.
Example:  python scripts/verify_public_web_access.py https://pilotmain.com
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure repo root on path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.chdir(_ROOT)

from app.services.web_access import (  # noqa: E402
    extract_visible_text,
    fetch_url,
    summarize_public_page,
)


def main() -> int:
    url = (sys.argv[1] if len(sys.argv) > 1 else "https://pilotmain.com").strip()
    if not url.startswith("http"):
        url = f"https://{url.lstrip()}"
    print("verify_public_web_access — url:", url, flush=True)
    s = summarize_public_page(url, allow_internal=False)
    if not s.ok:
        print("NOT_OK:", s.user_message or s.error, flush=True)
        return 1
    vis = (s.text_excerpt or "")[:2_000]
    print("TITLE:", s.title, flush=True)
    print("VISIBLE (excerpt):", vis[:1_200], "…" if len(vis) > 1_200 else "", flush=True)
    # quick fetch_url smoke
    f = fetch_url(url, allow_internal=False, respect_robots=True)
    print("FETCH status:", f.status_code, "err:", f.error, flush=True)
    if f.body_text:
        _ = extract_visible_text(f.body_text, max_chars=500)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
