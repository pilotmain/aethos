#!/usr/bin/env python3
"""Encrypt a single file for private artifact packaging (optional Fernet; dev utility).

Requires: ``pip install cryptography`` (not part of minimal OSS runtime).

Example::

    python scripts/build_pro_package.py --in path/to/module.py --out dist/module.enc
"""

from __future__ import annotations

import argparse
import sys


def _encrypt(path_in: str, path_out: str) -> bytes:
    try:
        from cryptography.fernet import Fernet
    except ImportError as e:
        raise SystemExit(
            "cryptography is required: pip install cryptography"
        ) from e

    key = Fernet.generate_key()
    cipher = Fernet(key)
    with open(path_in, "rb") as f:
        raw = f.read()
    encrypted = cipher.encrypt(raw)
    with open(path_out, "wb") as f:
        f.write(encrypted)
    print(f"Wrote {path_out} ({len(encrypted)} bytes).")
    print(
        "Store the Fernet key in a secrets manager; never commit it.\n"
        f"  key={key.decode()}"
    )
    return key


def main() -> None:
    p = argparse.ArgumentParser(description="Encrypt a file with Fernet (Pro packaging helper).")
    p.add_argument("--in", dest="path_in", required=True, help="Source file path")
    p.add_argument("--out", dest="path_out", required=True, help="Output encrypted path")
    args = p.parse_args()
    _encrypt(args.path_in, args.path_out)


if __name__ == "__main__":
    main()
