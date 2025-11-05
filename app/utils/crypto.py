"""Utility helpers for symmetric encryption of sensitive secrets."""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

_PREFIX = "enc::"


def _derive_key(secret: str) -> bytes:
    """Derive a stable Fernet-compatible key from the provided secret."""
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _get_cipher() -> Fernet:
    """Return a cached Fernet cipher instance using application settings."""
    config = current_app.config  # type: ignore[attr-defined]
    secret = config.get("INTEGRATION_SECRET_KEY") or config.get("SECRET_KEY")
    if not secret:
        raise RuntimeError("Missing INTEGRATION_SECRET_KEY or SECRET_KEY for encryption")
    key = _derive_key(secret)
    return Fernet(key)


def encrypt_value(value: Optional[str]) -> Optional[str]:
    """Encrypt a plaintext string, returning a token with a prefix marker."""
    if not value:
        return None
    cipher = _get_cipher()
    token = cipher.encrypt(value.encode("utf-8"))
    return f"{_PREFIX}{token.decode('utf-8')}"


def decrypt_value(value: Optional[str]) -> Optional[str]:
    """Decrypt a value if it is encrypted, otherwise return the original."""
    if not value:
        return None
    if not value.startswith(_PREFIX):
        return value
    token = value[len(_PREFIX):].encode("utf-8")
    cipher = _get_cipher()
    try:
        decrypted = cipher.decrypt(token)
    except InvalidToken:
        # Value was not encrypted with this key or is corrupted; treat as plaintext fallback.
        return value
    return decrypted.decode("utf-8")


def is_encrypted(value: Optional[str]) -> bool:
    """Check whether the stored value carries the encryption prefix."""
    return bool(value and value.startswith(_PREFIX))
