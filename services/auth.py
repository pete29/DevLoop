"""Signing in to the page with a password.

Streamlit listens on every network interface unless told
otherwise, so anyone on the same network could open the
page -- and with it the API key's budget, the GitHub token
and every registered repository. A password closes that.

Only a hash is kept, in .env as DEVLOOP_PASSWORD_HASH; the
password itself is never stored. Make one with:

    python -m services.auth
"""

import base64
import getpass
import hashlib
import hmac
import os
import secrets
import time

VARIABLE = "DEVLOOP_PASSWORD_HASH"

ALGORITHM = "pbkdf2_sha256"

# OWASP's figure for PBKDF2-HMAC-SHA256: slow enough to make
# guessing a stolen hash expensive, about half a second here.
ITERATIONS = 600_000

# Failures in a row before signing in is refused for a while.
MAX_FAILURES = 5

LOCK_SECONDS = 60

# Per process, not per session: a reload starts a new
# session, so a per-session count would reset on F5.
_failures = 0

_locked_until = 0.0


def _encode(raw: bytes) -> str:

    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(text: str) -> bytes:

    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    """The line to store: algorithm, iterations, salt, hash.

    ':'-separated and base64 without padding, so it needs no
    quoting in .env.
    """

    salt = secrets.token_bytes(16)

    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)

    return f"{ALGORITHM}:{iterations}:{_encode(salt)}:{_encode(digest)}"


def matches(password: str, stored: str) -> bool:
    """Whether the password is the one the hash was made from."""

    try:
        algorithm, iterations, salt, expected = stored.strip().split(":")

        if algorithm != ALGORITHM:
            return False

        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            _decode(salt),
            int(iterations),
        )

    except (ValueError, TypeError):
        return False

    # Constant time: how long a comparison takes must not
    # say how much of a guess was right.
    return hmac.compare_digest(digest, _decode(expected))


def stored_hash() -> str:
    """The hash from the environment, or "" when none is set."""

    return (os.getenv(VARIABLE) or "").strip()


def required() -> bool:
    """Whether the page asks for a password at all."""

    return bool(stored_hash())


def seconds_locked() -> int:
    """How long signing in is still refused, 0 when it is not."""

    return max(0, int(_locked_until - time.time() + 0.999))


def sign_in(password: str) -> bool:
    """Checks a password, counting failures.

    While locked every attempt fails, the right password
    included, so guessing gains nothing by trying faster.
    """

    global _failures, _locked_until

    if seconds_locked():
        return False

    if matches(password, stored_hash()):
        _failures = 0
        return True

    _failures += 1

    if _failures >= MAX_FAILURES:
        _failures = 0
        _locked_until = time.time() + LOCK_SECONDS

    return False


def reset() -> None:
    """Forgets failures and locks; for the tests."""

    global _failures, _locked_until

    _failures = 0

    _locked_until = 0.0


def main() -> None:

    password = getpass.getpass("New DevLoop password: ")

    if len(password) < 8:
        raise SystemExit("Use at least 8 characters.")

    if getpass.getpass("Again: ") != password:
        raise SystemExit("The two did not match.")

    print()
    print("Add this line to .env, then restart DevLoop:")
    print()
    print(f"{VARIABLE}={hash_password(password)}")


if __name__ == "__main__":
    main()
