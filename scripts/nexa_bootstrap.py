#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""
One-command Nexa setup. Run from the repo root:

  python scripts/nexa_bootstrap.py

  python scripts/nexa_bootstrap.py --doctor
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.nexa_bootstrap import main

if __name__ == "__main__":
    raise SystemExit(main())
