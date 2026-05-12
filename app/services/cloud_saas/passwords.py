# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2025 AethOS AI

"""Password hashing for cloud registration / login."""

from __future__ import annotations

from passlib.context import CryptContext

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd.hash(plain)


def verify_password(plain: str, password_hash: str) -> bool:
    return _pwd.verify(plain, password_hash)


__all__ = ["hash_password", "verify_password"]
