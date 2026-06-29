"""Authentication module for the demo app.

Handles password hashing and login token issuance. Intentionally tiny so
MEMBERRY can ingest it in seconds during a judge demo.
"""

import hashlib
import secrets

_TOKENS: dict[str, str] = {}


def hash_password(password: str, salt: str) -> str:
    """Return a salted SHA-256 hex digest of ``password``."""
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def issue_token(username: str) -> str:
    """Create and store a random session token for ``username``."""
    token = secrets.token_hex(16)
    _TOKENS[token] = username
    return token


def whoami(token: str) -> str | None:
    """Return the username for a valid token, or ``None``."""
    return _TOKENS.get(token)
