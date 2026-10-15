"""Offline check: the settings panel and the .env it writes.

The real page, headless, against a throwaway database and a
throwaway .env; no key is real and nothing is sent:

    python -m tests.settings_test
"""

import os
import shutil
import tempfile

folder = tempfile.mkdtemp()

os.environ["DEVLOOP_DATABASE"] = os.path.join(folder, "settings.db")

# A password in the developer's .env would stop the page at
# the sign-in screen; set, even empty, .env does not override it.
os.environ["DEVLOOP_PASSWORD_HASH"] = ""

for name in ("ANTHROPIC_API_KEY", "GITHUB_PAT", "GITHUB_ADMIN_PAT", "DEVLOOP_MONTH_LIMIT"):
    os.environ[name] = ""

from streamlit.testing.v1 import AppTest  # noqa: E402

from services import env_file  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


def refuses(label: str, name: str, value: str) -> None:

    try:
        env_file.check(name, value)

    except env_file.SettingError:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: was accepted")


def read() -> str:

    with open(env_file.ENV_PATH, encoding="utf-8") as handle:
        return handle.read()


KEY = "sk-ant-api03-" + "x" * 95

TOKEN = "github_pat_" + "y" * 82

try:

    env_file.ENV_PATH = os.path.join(folder, ".env")

    with open(env_file.ENV_PATH, "w", encoding="utf-8") as handle:
        handle.write("# my keys\nANTHROPIC_API_KEY=old\nOTHER=kept\nANTHROPIC_API_KEY=duplicate\n")

    print("=" * 80)
    print("ONE LINE CHANGES, THE REST STAYS")
    print("=" * 80)

    env_file.save("ANTHROPIC_API_KEY", KEY)

    check(
        "the key is replaced once, comments and other lines kept",
        read(),
        f"# my keys\nANTHROPIC_API_KEY={KEY}\nOTHER=kept\n",
    )

    check("and it is in effect at once", os.environ["ANTHROPIC_API_KEY"], KEY)

    env_file.save("GITHUB_PAT", TOKEN)

    check("a new one is added at the end", read().endswith(f"GITHUB_PAT={TOKEN}\n"), True)

    check("a key is described, never shown", env_file.describe("GITHUB_PAT"), "github_pat_… (93)")

    env_file.save("GITHUB_PAT", "")

    check("clearing empties it", ("GITHUB_PAT=\n" in read(), os.getenv("GITHUB_PAT")), (True, None))

    print()
    print("=" * 80)
    print("WHAT IS REFUSED")
    print("=" * 80)

    refuses("a line break, which would add a setting", "GITHUB_PAT", "github_pat_a\nEVIL=1")

    refuses("a quote", "GITHUB_PAT", 'github_pat_"a')

    refuses("a key of the wrong kind", "ANTHROPIC_API_KEY", "github_pat_abc")

    refuses("a limit that is not a number", "DEVLOOP_MONTH_LIMIT", "five")

    refuses("a negative limit", "DEVLOOP_MONTH_LIMIT", "-1")

    refuses("a setting the panel does not own", "DEVLOOP_DATABASE", "x.db")

    check("surrounding spaces are trimmed", env_file.check("DEVLOOP_MONTH_LIMIT", " 2.5 "), "2.5")

    print()
    print("=" * 80)
    print("THE PANEL")
    print("=" * 80)

    app = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")

    at = AppTest.from_file(app, default_timeout=60)

    at.run()

    check("English by default", at.session_state.language, "en")

    [b for b in at.sidebar.button if b.key == "settings-open"][0].click().run()

    check("the page did not fail", [e.value for e in at.exception], [])

    check(
        "no password section for now",
        any(b.label == "Remove the password" for b in at.button),
        False,
    )

    shown = " ".join(item.value for item in at.caption)

    check("the saved key is not on the page", KEY in shown, False)

    check("but that it is set, and how it starts, is", "sk-ant-… (108)" in shown, True)

    limit_field = [item for item in at.text_input if item.help and "no limit" in item.help][0]

    limit_field.input("3")

    [b for b in at.button if b.label == "💾 Save" and b.form_id == "setting-DEVLOOP_MONTH_LIMIT"][0].click().run()

    check("the page did not fail", [e.value for e in at.exception], [])

    check("the limit is written", "DEVLOOP_MONTH_LIMIT=3\n" in read(), True)

    from config.settings import Settings

    check("and in effect", Settings.MONTH_COST_LIMIT, 3.0)

    print()
    print("=" * 80)
    print("THE LANGUAGE IS REMEMBERED")
    print("=" * 80)

    at.selectbox(key="language_select").set_value("pl").run()

    check("switched", at.session_state.language, "pl")

    again = AppTest.from_file(app, default_timeout=60)

    again.run()

    check("a new session keeps it", again.session_state.language, "pl")

    Settings.MONTH_COST_LIMIT = 0

finally:
    shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL SETTINGS CHECKS PASSED")
print("=" * 80)
