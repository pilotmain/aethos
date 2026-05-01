"""
Encrypt and decrypt per-user values with a server-side secret.
Uses Fernet with a key derived from NEXA_SECRET_KEY (never log it).
"""
from __future__ import annotations

import base64
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_SALT = b"nexa-byok-v1"
_PBKDF2_ITER = 200_000


def _fernet() -> Fernet:
    s = get_settings()
    raw = (s.nexa_secret_key or (os.environ.get("NEXA_SECRET_KEY") or "")).strip()
    if not raw or len(raw) < 8:
        raise ValueError("NEXA_SECRET_KEY is not set or too short; cannot use encrypted storage")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=_PBKDF2_ITER,
    )
    key = base64.urlsafe_b64encode(kdf.derive(raw.encode("utf-8")))
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    if plaintext is None:
        raise TypeError("plaintext is required")
    t = _fernet()
    b = t.encrypt(plaintext.encode("utf-8"))
    return b.decode("ascii")


def decrypt(ciphertext: str) -> str:
    t = _fernet()
    try:
        b = t.decrypt(ciphertext.encode("ascii"))
        return b.decode("utf-8")
    except InvalidToken as e:
        logger.error("decrypt failed (InvalidToken)")
        raise ValueError("Could not decrypt stored value; wrong NEXA_SECRET_KEY?") from e


def is_configured() -> bool:
    s = get_settings()
    w = (s.nexa_secret_key or "").strip() or (os.environ.get("NEXA_SECRET_KEY") or "").strip()
    return len(w) >= 8
