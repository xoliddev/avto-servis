"""Servis pasporti links.

A link token is 12 random bytes followed by the first 12 bytes of HMAC-SHA256(secret, "pasport:" + nonce), in
URL-safe base64: 32 characters, 96 random bits. The signature is checked in constant time *before* the database is
asked, so a guessed or altered link costs nothing and tells nothing; expiry and revocation live in the database.
shared/token.js is the same code (with a small SHA-256) for the browser demo.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re

TOKEN_LEN = 32
_SHAPE = re.compile(r"^[A-Za-z0-9_-]{32}$")


def secret_from(seed: str) -> bytes:
    """The signing key, derived from SHARE_SECRET (or the bot token when none is set)."""
    return hmac.new(b"avtoservis-pasport", seed.encode(), hashlib.sha256).digest()


def _sig(secret: bytes, nonce: bytes) -> bytes:
    return hmac.new(secret, b"pasport:" + nonce, hashlib.sha256).digest()[:12]


def make(secret: bytes, nonce: bytes) -> str:
    return base64.urlsafe_b64encode(nonce + _sig(secret, nonce)).decode()


def nonce_of(secret: bytes, token: object) -> str | None:
    """The nonce (hex) of a well-formed, correctly signed token, else None."""
    if not isinstance(token, str) or not _SHAPE.match(token):
        return None
    raw = base64.urlsafe_b64decode(token)
    nonce, sig = raw[:12], raw[12:]
    return nonce.hex() if hmac.compare_digest(sig, _sig(secret, nonce)) else None
