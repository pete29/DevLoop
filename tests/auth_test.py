"""Offline check: the password, its hash, and the sign-in screen.

The real page, headless, against a throwaway database:

    python -m tests.auth_test
"""

import os
import shutil
import tempfile

folder = tempfile.mkdtemp()

os.environ["DEVLOOP_DATABASE"] = os.path.join(folder, "auth.db")

from streamlit.testing.v1 import AppTest  # noqa: E402

from services import auth  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


def sign_in(at: AppTest, password: str) -> None:

    at.text_input[0].input(password)

    at.button[0].click().run()


try:

    print("=" * 80)
    print("ONLY A HASH IS KEPT")
    print("=" * 80)

    # Few iterations: the count is stored in the hash, so
    # this checks the same code at a fraction of the time.
    stored = auth.hash_password("correct horse", iterations=1000)

    check("the password is not in it", "correct horse" in stored, False)

    check("it has algorithm, iterations, salt and hash", stored.split(":")[:2], ["pbkdf2_sha256", "1000"])

    check("nothing in it needs quoting in .env", any(c in stored for c in "$#'\" ="), False)

    check("the right password matches", auth.matches("correct horse", stored), True)

    check("a wrong one does not", auth.matches("correct horsE", stored), False)

    check("the same password hashes differently each time", stored == auth.hash_password("correct horse", 1000), False)

    check("a damaged hash matches nothing", auth.matches("correct horse", "pbkdf2_sha256:x"), False)

    print()
    print("=" * 80)
    print("WITHOUT A PASSWORD THE PAGE IS OPEN")
    print("=" * 80)

    os.environ[auth.VARIABLE] = ""

    app = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")

    at = AppTest.from_file(app, default_timeout=60)

    at.run()

    check("the page did not fail", [e.value for e in at.exception], [])

    check("no sign-in form", len(at.text_input) > 0 and at.text_input[0].label in ("Hasło", "Password"), False)

    check("and no sign-out button", [b for b in at.sidebar.button if b.key == "logout"], [])

    print()
    print("=" * 80)
    print("WITH ONE, NOTHING SHOWS BEFORE IT IS GIVEN")
    print("=" * 80)

    os.environ[auth.VARIABLE] = stored

    auth.reset()

    at = AppTest.from_file(app, default_timeout=60)

    at.run()

    check("the page did not fail", [e.value for e in at.exception], [])

    check("only the password is asked for", [item.label for item in at.text_input], ["Password"])

    check("the sidebar is empty", len(at.sidebar.button), 0)

    sign_in(at, "wrong")

    check("a wrong password is refused", [item.value for item in at.error], ["Wrong password."])

    check("and the page stays closed", at.session_state.signed_in if "signed_in" in at.session_state else False, False)

    sign_in(at, "correct horse")

    check("the right one opens the page", at.session_state.signed_in, True)

    check("which then draws", len(at.sidebar.button) > 0, True)

    [b for b in at.sidebar.button if b.key == "logout"][0].click().run()

    check("signing out closes it again", [item.label for item in at.text_input], ["Password"])

    print()
    print("=" * 80)
    print("GUESSING IS SLOWED DOWN")
    print("=" * 80)

    auth.reset()

    for _ in range(auth.MAX_FAILURES):
        auth.sign_in("guess")

    check("after the limit, signing in is locked", auth.seconds_locked() > 0, True)

    check("even the right password is refused while locked", auth.sign_in("correct horse"), False)

    at = AppTest.from_file(app, default_timeout=60)

    at.run()

    check("the page says to wait", len(at.warning), 1)

    auth.reset()

    check("once the lock is over, it works", auth.sign_in("correct horse"), True)

finally:
    os.environ.pop(auth.VARIABLE, None)
    shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL AUTH CHECKS PASSED")
print("=" * 80)
