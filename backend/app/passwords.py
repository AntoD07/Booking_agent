"""Password hashing for band logins.

Uses the standard library's PBKDF2-HMAC-SHA256 so no extra dependency is
needed for a single-service app with a handful of shared band passwords.
A stored hash is `pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>`.
"""

import hashlib
import secrets

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 240_000


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt, _ITERATIONS
    )
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, hash_hex = stored.split("$")
        if algorithm != _ALGORITHM:
            return False
        expected = bytes.fromhex(hash_hex)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(digest, expected)
