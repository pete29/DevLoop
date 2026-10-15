"""Offline check: the page will not register a folder nothing can run in.

The real page, rendered headlessly against a throwaway
database and throwaway folders:

    python -m tests.repository_form_test
"""

import os
import shutil
import tempfile

folder = tempfile.mkdtemp()

os.environ["DEVLOOP_DATABASE"] = os.path.join(folder, "form.db")

# A password in the developer's .env would stop the page at
# the sign-in screen; set, even empty, .env does not override it.
os.environ["DEVLOOP_PASSWORD_HASH"] = ""

from streamlit.testing.v1 import AppTest  # noqa: E402

from database.repository_repository import RepositoryRepository  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


def button(at: AppTest, key: str):

    return [item for item in at.button if item.key == key][0]


try:

    plain = os.path.join(folder, "plain")

    os.makedirs(os.path.join(plain, "src"))

    app = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")

    at = AppTest.from_file(app, default_timeout=60)

    at.run()

    print("=" * 80)
    print("A FOLDER WITHOUT GIT")
    print("=" * 80)

    at.session_state.repo_add_path = plain

    at.session_state.repo_add_name = "plain"

    at.run()

    check("the page did not fail", [e.value for e in at.exception], [])

    check(
        "it says the folder is not a repository",
        any("git" in item.value for item in at.warning),
        True,
    )

    check("adding it is not offered", button(at, "repo-add").disabled, True)

    button(at, "repo-add-git-init").click().run()

    check("git init made it one", os.path.isdir(os.path.join(plain, ".git")), True)

    print()
    print("=" * 80)
    print("A FOLDER INSIDE A REPOSITORY")
    print("=" * 80)

    at.session_state.repo_add_path = os.path.join(plain, "src")

    at.run()

    check("adding the subfolder is not offered", button(at, "repo-add").disabled, True)

    button(at, "repo-add-use-root").click().run()

    check(
        "the repository's own folder is offered instead",
        os.path.normcase(at.session_state.repo_add_path),
        os.path.normcase(plain),
    )

    print()
    print("=" * 80)
    print("A REPOSITORY")
    print("=" * 80)

    check("now it can be added", button(at, "repo-add").disabled, False)

    button(at, "repo-add").click().run()

    check(
        "and it is registered",
        [item.name for item in RepositoryRepository().get_all()],
        ["plain"],
    )

finally:
    shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL REPOSITORY FORM CHECKS PASSED")
print("=" * 80)
