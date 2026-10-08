"""Password hashing and session tokens for Campus Customs.

The seeded `users` rows already store passwords as

    pbkdf2_sha256$<salt>$<hex digest>

derived with PBKDF2-HMAC-SHA256, 120,000 iterations, over the salt's raw UTF-8
bytes. New accounts are written in exactly that format so old and new rows stay
verifiable by the same code path.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 120_000
SALT_BYTES = 8  # 16 hex chars, matching the existing rows

SESSION_TTL_SECONDS = 60 * 60 * 24 * 7  # one week

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------


def _derive(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), ITERATIONS
    ).hex()


def hash_password(password: str) -> str:
    """Return a storable `algorithm$salt$digest` string with a fresh random salt."""
    salt = secrets.token_hex(SALT_BYTES)
    return f"{ALGORITHM}${salt}${_derive(password, salt)}"


def verify_password(password: str, stored: str) -> bool:
    """Check a password against a stored hash in constant time."""
    try:
        algorithm, salt, digest = stored.split("$", 2)
    except (AttributeError, ValueError):
        return False
    if algorithm != ALGORITHM:
        return False
    return hmac.compare_digest(_derive(password, salt), digest)


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def normalize_email(email: str) -> str:
    """Emails are matched case-insensitively; `users.email` is UNIQUE."""
    return (email or "").strip().lower()


def password_problem(password: str) -> str | None:
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    return None


def email_problem(email: str) -> str | None:
    if not EMAIL_RE.match(normalize_email(email)):
        return "Enter a valid email address."
    return None


# --------------------------------------------------------------------------
# Session tokens
# --------------------------------------------------------------------------
#
# Stateless HMAC-signed tokens: `<base64url payload>.<base64url signature>`.
# The payload carries the user id and an expiry, so there is no session table to
# add and a restart does not log everyone out. The signature is what makes the
# payload trustworthy -- it is not encryption, so nothing secret goes inside.

SECRET = os.environ.get("CAMPUS_CUSTOMS_SECRET", "dev-secret-change-in-production").encode()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def create_token(user_id: int) -> str:
    payload = _b64(json.dumps({"uid": user_id, "exp": int(time.time()) + SESSION_TTL_SECONDS}).encode())
    signature = _b64(hmac.new(SECRET, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def read_token(token: str | None) -> int | None:
    """Return the user id for a valid, unexpired token, else None."""
    if not token:
        return None
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return None

    expected = _b64(hmac.new(SECRET, payload.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        return None

    try:
        data = json.loads(_unb64(payload))
    except (ValueError, json.JSONDecodeError):
        return None

    if data.get("exp", 0) < time.time():
        return None
    return data.get("uid")
