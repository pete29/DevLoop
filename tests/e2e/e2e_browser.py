"""The real page in a real browser.

DevLoop's own server, started on a free port against a
throwaway database, and Chromium clicking through it: what a
headless render cannot show -- that the page loads at all in
a browser, the dialogs and expanders open, the widgets take
typing. Nothing here calls a model or GitHub.

Needs Playwright's Chromium (`python -m playwright install
chromium`); skipped without it.
"""

import os
import socket
import subprocess
import sys
import time

import pytest
import requests

pytestmark = [pytest.mark.e2e, pytest.mark.browser]

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def free_port() -> int:

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def server(workspace):
    """DevLoop, served on localhost only, until the test ends."""

    port = free_port()

    environment = {
        **os.environ,
        "DEVLOOP_DATABASE": str(workspace / "browser.db"),
        "PYTHONPATH": ROOT,
        "PYTHONUTF8": "1",
    }

    process = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", os.path.join(ROOT, "app.py"),
            "--server.headless", "true",
            "--server.address", "127.0.0.1",
            "--server.port", str(port),
            "--browser.gatherUsageStats", "false",
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    url = f"http://127.0.0.1:{port}"

    try:
        deadline = time.monotonic() + 60

        while time.monotonic() < deadline:
            try:
                if requests.get(f"{url}/_stcore/health", timeout=2).ok:
                    break
            except requests.RequestException:
                time.sleep(0.5)
        else:
            pytest.fail("DevLoop's server did not start within a minute")

        yield url

    finally:
        process.terminate()
        process.wait(timeout=30)


@pytest.fixture
def page(server):

    sync = pytest.importorskip("playwright.sync_api")

    with sync.sync_playwright() as playwright:

        try:
            browser = playwright.chromium.launch()

        except Exception as error:  # noqa: BLE001
            pytest.skip(f"no Chromium for Playwright: {error}")

        page = browser.new_page()

        page.set_default_timeout(30_000)

        page.goto(server)

        yield page

        browser.close()


def no_exception(page) -> None:
    """Streamlit draws a failing script as an exception box."""

    assert page.locator('[data-testid="stException"]').count() == 0


def choose(page, label: str, option: str) -> None:
    """Picks an option from a selectbox.

    Its list closes whenever the page redraws, which a
    background refresh can do at any moment, so opening and
    picking are tried again a few times.
    """

    box = page.locator('[data-testid="stSelectbox"]').filter(has_text=label)

    for _ in range(5):

        box.get_by_role("button", name="Open").click()

        choice = page.get_by_role("option", name=option)

        try:
            choice.click(timeout=3_000)
            return

        except Exception:  # noqa: BLE001 -- the list closed under us
            page.keyboard.press("Escape")

    raise AssertionError(f"could not choose {option!r} in {label!r}")


def test_the_page_works_in_a_browser(page, workspace):

    from config.version import VERSION

    # ------------------------------------------------ it loads, and says which version

    page.get_by_role("heading", name="DevLoop").first.wait_for()

    page.get_by_text(f"v{VERSION}").first.wait_for()

    no_exception(page)

    # ------------------------------------------------ a repository is added by typing its path

    folder = workspace / "typed-repository"

    folder.mkdir()

    subprocess.run(["git", "init", "--quiet", str(folder)], check=True)

    page.get_by_text("Add repository").first.click()

    path_field = page.get_by_role("textbox", name="Path", exact=True)

    path_field.fill(str(folder))

    path_field.press("Enter")

    # The name follows the path once the page has taken it.
    from playwright.sync_api import expect

    expect(page.get_by_role("textbox", name="Name", exact=True)).to_have_value("typed-repository")

    page.get_by_role("button", name="Add", exact=True).click()

    page.get_by_text("Added the repository typed-repository").wait_for()

    no_exception(page)

    # ------------------------------------------------ a requirement is written and saved

    page.get_by_role("button", name="New requirement").click()

    page.get_by_role("textbox", name="Title", exact=True).fill("Calendar date arithmetic")

    page.get_by_role("textbox", name="Requirements description", exact=True).fill("Add days to a date, and tell its weekday.")

    page.get_by_role("button", name="💾 Save").first.click()

    page.locator('[data-testid="stSidebar"]').get_by_role("button", name="Calendar date arithmetic").wait_for()

    no_exception(page)

    # ------------------------------------------------ the settings switch the language

    page.get_by_role("button", name="⚙️ Settings").click()

    page.get_by_role("heading", name="⚙️ Settings").wait_for()

    page.get_by_text("Not set", exact=True).first.wait_for()

    choose(page, "Language", "Polski")

    page.get_by_role("button", name="⚙️ Ustawienia").wait_for()

    no_exception(page)
