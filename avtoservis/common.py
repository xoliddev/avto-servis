"""Small shared pieces: the refusal error and one-time workshop invite links."""

from __future__ import annotations

import hashlib
import re
import secrets

LINK = re.compile(r"^[A-Za-z0-9_-]{22}$")  # 16 random bytes, URL-safe base64: 128 bits


class Refused(Exception):
    """An action that is not allowed; ``code`` maps to an ``err.<code>`` text."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def new_link() -> str:
    return secrets.token_urlsafe(16)


def link_hash(token: str) -> str:
    """Workshop invite links are looked up by their SHA-256, so the lookup itself leaks nothing about other links;
    only the hash is stored."""
    return hashlib.sha256(token.encode()).hexdigest()
