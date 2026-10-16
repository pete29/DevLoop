"""Offline check: the first-run page.

The real page, headless, against a throwaway database and a
throwaway .env; no key is real and nothing is sent:

    python -m tests.first_run_test
"""

import os
import shutil
import tempfile

folder = tempfile.mkdtemp()

os.environ["DEVLOOP_DATABASE"] = os.path.join(folder, "first.db")

# A password in the developer's .env would stop the page at
# the sign-in screen; set, even empty, .env does not override it.
os.environ["DEVLOOP_PASSWORD_HASH"] = ""

# The runners switch the page off for every other suite.
os.environ.pop("DEVLOOP_FIRST_RUN", None)

for name in ("ANTHROPIC_API_KEY", "GITHUB_PAT", "GITHUB_ADMIN_PAT"):
    os.environ[name] = ""

from streamlit.testing.v1 import AppTest  # noqa: E402

from services import env_file, first_run  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


def page() -> AppTest:

    app = AppTest.from_file("../app.py", default_timeout=60)

    app.run()

    return app


def texts(app: AppTest) -> str:

    return " ".join(
        [item.value for item in app.markdown]
        + [item.value for item in app.subheader]
        + [item.value for item in app.caption]
    )


try:

    env_file.ENV_PATH = os.path.join(folder, ".env")

    print("=" * 80)
    print("WHAT IS CHECKED")
    print("=" * 80)

    check("git found", first_run.git_check("git version 2.47.0").ok, True)

    check("git missing", (first_run.git_check("").ok, first_run.git_check("").detail), (False, "not found on PATH"))

    check("a current Node.js", first_run.node_check("v24.1.0").ok, True)

    old = first_run.node_check("v16.20.2")

    check("an old Node.js is not enough, and says why", (old.ok, "18 or newer" in old.detail), (False, True))

    check("the GitHub token is optional", first_run.ready([first_run.Check("GITHUB_PAT", False, False)]), True)

    check("the Anthropic key is not", first_run.ready([first_run.Check("ANTHROPIC_API_KEY", False, True)]), False)

    print()
    print("=" * 80)
    print("WITHOUT A KEY, THE PAGE SAYS WHAT IS MISSING")
    print("=" * 80)

    app = page()

    check("the first-run page stands in front", "Before you start" in texts(app), True)

    check("the key can be set right there", any(form.key == "setting-ANTHROPIC_API_KEY" for form in app.get("form")), True)

    check("the rest of the page is not drawn", "Requirements" in texts(app), False)

    app.button(key="first-run-anyway").click().run()

    check("it can be passed over", "Before you start" in texts(app), False)

    print()
    print("=" * 80)
    print("WITH EVERYTHING THERE, IT IS NOT SHOWN")
    print("=" * 80)

    env_file.save("ANTHROPIC_API_KEY", "sk-ant-api03-" + "x" * 95)

    app = page()

    passed = first_run.ready(first_run.checks())

    check(
        "with git, Node.js and the key, the page opens directly",
        "Before you start" in texts(app),
        not passed,
    )

finally:
    shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL FIRST RUN CHECKS PASSED")
print("=" * 80)
