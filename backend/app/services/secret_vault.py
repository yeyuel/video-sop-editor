from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

ENCRYPTED_PREFIX = "enc:v1:"


def _fernet() -> Fernet:
    raw = settings.resolved_app_secret_key.encode("utf-8")
    digest = hashlib.sha256(raw).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def is_encrypted(value: str) -> bool:
    return value.startswith(ENCRYPTED_PREFIX)


def encrypt_secret(plaintext: str) -> str:
    text = plaintext.strip()
    if not text:
        return ""
    if is_encrypted(text):
        return text
    token = _fernet().encrypt(text.encode("utf-8")).decode("utf-8")
    return f"{ENCRYPTED_PREFIX}{token}"


def decrypt_secret(stored: str) -> str:
    text = stored.strip()
    if not text:
        return ""
    if not is_encrypted(text):
        return text
    payload = text[len(ENCRYPTED_PREFIX) :]
    try:
        return _fernet().decrypt(payload.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""


def encrypt_api_key_if_needed(plaintext: str) -> str:
    return encrypt_secret(plaintext)


def decrypt_api_key_if_needed(stored: str) -> str:
    return decrypt_secret(stored)
