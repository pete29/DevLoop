"""DevLoop's entry point in the exe: an application window of its own.

    DevLoop.exe                 the window, and the page server behind it
    DevLoop.exe --serve <port>  the page server alone (started by the window)
    DevLoop.exe --worker <id>   one background run (started by the page)

The window is WebView2, the engine built into Windows: no
browser around it, and closing it stops DevLoop. Without
WebView2 the page opens in an Edge app window instead, and
DevLoop runs until its log window is closed. The page listens
on 127.0.0.1 alone, never on the network: it holds the API
keys and can write to any folder. A second start while one is
running opens a window on it rather than a second server on
the same database. The server's log is launcher.log in the
data folder.

DEVLOOP_NO_BROWSER=1 serves in the foreground and opens
nothing, for a smoke test. From source the same file works
too: python launcher.py.
"""

import os
import socket
import subprocess
import sys
import time
import webbrowser

from config import paths

HOST = "127.0.0.1"

# The port Streamlit is used to, when it is free.
PREFERRED_PORT = 8501

PORT_FILE = "launcher.port"

LOG_FILE = "launcher.log"

TITLE = "DevLoop"

# How long the window waits for the page server to answer.
START_SECONDS = 120

# How long a native window may take to show the page before
# it is taken for broken and Edge is used instead.
LOAD_SECONDS = 15

# WebView2's Evergreen runtime, as Windows registers it.
WEBVIEW2_CLIENT = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"


def port_file() -> str:

    return os.path.join(paths.home(), PORT_FILE)


def answering(port: int) -> bool:
    """Whether something is listening on this computer's port."""

    try:
        with socket.create_connection((HOST, port), timeout=0.5):
            return True

    except OSError:
        return False


def running_port() -> int:
    """The port of a DevLoop already running, or 0."""

    try:
        with open(port_file(), encoding="utf-8") as handle:
            port = int(handle.read().strip() or 0)

    except (OSError, ValueError):
        return 0

    return port if port and answering(port) else 0


def free_port() -> int:
    """The preferred port if nothing holds it, else one the system picks."""

    if not answering(PREFERRED_PORT):
        return PREFERRED_PORT

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((HOST, 0))
        return probe.getsockname()[1]


def edge() -> str:
    """Microsoft Edge, for a window of its own, or ""."""

    for base in (os.getenv("ProgramFiles(x86)"), os.getenv("ProgramFiles")):

        if not base:
            continue

        candidate = os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe")

        if os.path.isfile(candidate):
            return candidate

    return ""


def webview2_folders() -> list[str]:
    """Where the WebView2 runtime keeps its versions, machine-wide and per user."""

    found = []

    for base in (os.getenv("ProgramFiles(x86)"), os.getenv("ProgramFiles"), os.getenv("LOCALAPPDATA")):
        if base:
            found.append(os.path.join(base, "Microsoft", "EdgeWebView", "Application"))

    return found


def webview2_versions() -> list[str]:
    """The WebView2 versions Windows says are installed."""

    if os.name != "nt":
        return []

    import winreg

    versions = []

    for root, key in (
        (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\WOW6432Node\\" + WEBVIEW2_CLIENT),
        (winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\\" + WEBVIEW2_CLIENT),
        (winreg.HKEY_CURRENT_USER, "Software\\" + WEBVIEW2_CLIENT),
    ):
        try:
            with winreg.OpenKey(root, key) as handle:
                version = str(winreg.QueryValueEx(handle, "pv")[0] or "")

        except OSError:
            continue

        if version and version != "0.0.0.0":
            versions.append(version)

    return versions


def webview2_ready(versions: list[str] | None = None, folders: list[str] | None = None) -> bool:
    """Whether a WebView2 runtime is registered and its files are there.

    Registered is not enough: on the author's machine the
    registry named 151.0.4129.78 while its folder was empty,
    and the window stayed blank (#82).
    """

    versions = webview2_versions() if versions is None else versions

    folders = webview2_folders() if folders is None else folders

    return any(
        os.path.isfile(os.path.join(folder, version, "msedgewebview2.exe"))
        for version in versions
        for folder in folders
    )


def open_app_window(url: str) -> subprocess.Popen | None:
    """The page in an Edge app window that closes with DevLoop, or None.

    A profile of its own in the data folder makes the window
    its own Edge process: when it exits, the window was
    closed, and DevLoop stops with it.
    """

    browser = edge()

    if not browser:
        return None

    profile = os.path.join(paths.home(), "window-profile")

    try:
        return subprocess.Popen(
            [browser, f"--app={url}", f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check"],
            close_fds=True,
        )

    except OSError:
        return None


def open_page(url: str) -> None:
    """The page in a window of its own where Edge exists, else a browser tab.

    DEVLOOP_NO_BROWSER=1 serves without opening anything: for
    a smoke test of the exe, or a page opened by hand.
    """

    if (os.getenv("DEVLOOP_NO_BROWSER") or "").strip() == "1":
        return

    browser = edge()

    if browser:
        try:
            subprocess.Popen([browser, f"--app={url}"], close_fds=True)
            return

        except OSError:
            pass

    webbrowser.open(url)


def streamlit_arguments(port: int) -> list[str]:
    """`streamlit run` for the page, bound to this computer only."""

    return [
        "streamlit",
        "run",
        os.path.join(paths.ROOT, "app.py"),
        f"--server.address={HOST}",
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--global.developmentMode=false",
        # No "Deploy" button: this page is not for the cloud.
        "--client.toolbarMode=minimal",
        # Source files never change inside the exe.
        "--server.fileWatcherType=none",
    ]


def self_command(*arguments: str) -> list[str]:
    """This program again, with arguments: the exe, or launcher.py from source."""

    if paths.frozen():
        return [sys.executable, *arguments]

    return [sys.executable, os.path.abspath(__file__), *arguments]


def start_server(port: int) -> subprocess.Popen:
    """The page server, in a process of its own, logging to the data folder."""

    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    log = open(os.path.join(paths.home(), LOG_FILE), "a", encoding="utf-8")

    return subprocess.Popen(
        self_command("--serve", str(port)),
        stdout=log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
        creationflags=flags,
    )


def wait_for(port: int, server: subprocess.Popen | None = None, seconds: float = START_SECONDS) -> bool:
    """Whether the page answers before the time runs out or the server dies."""

    deadline = time.monotonic() + seconds

    while time.monotonic() < deadline:

        if answering(port):
            return True

        if server is not None and server.poll() is not None:
            return False

        time.sleep(0.3)

    return False


def show_window(url: str) -> bool:
    """The page in a native window until it is closed; False if it cannot show it.

    pywebview does not raise when WebView2 fails to start:
    it shows an empty window (#82). So the runtime is looked
    for first, and a window whose page has not loaded in
    LOAD_SECONDS is closed and reported as a failure.
    """

    if not webview2_ready():
        print("WebView2 is not installed (or its files are missing); opening Edge instead.")
        return False

    loaded = {"ok": False}

    try:
        import webview

        window = webview.create_window(TITLE, url, width=1400, height=900, min_size=(900, 600))

        def watch() -> None:
            if window.events.loaded.wait(LOAD_SECONDS):
                loaded["ok"] = True
                return
            print("The window did not load the page; opening Edge instead.")
            window.destroy()

        webview.start(watch)

    except Exception as error:  # noqa: BLE001 -- any failure means: no window here
        print(f"No native window ({error}); opening Edge instead.")
        return False

    return loaded["ok"]


def application() -> None:
    """The window, and the page server behind it, which stops with it."""

    os.makedirs(paths.home(), exist_ok=True)

    running = running_port()

    if running:
        url = f"http://{HOST}:{running}"
        if not show_window(url):
            open_app_window(url) or open_page(url)
        return

    port = free_port()

    with open(port_file(), "w", encoding="utf-8") as handle:
        handle.write(str(port))

    server = start_server(port)

    try:
        if not wait_for(port, server):
            notify_failure()
            return

        url = f"http://{HOST}:{port}"

        if show_window(url):
            return

        window = open_app_window(url)

        if window is not None:
            # Its own Edge process: closing the window ends it.
            window.wait()
            return

        open_page(url)

        # A browser tab is not ours to watch: DevLoop runs as
        # long as its server.
        server.wait()

    finally:
        if server.poll() is None:
            server.terminate()

        try:
            os.remove(port_file())
        except OSError:
            pass


def notify_failure() -> None:
    """Says the page did not start, where a windowed exe can still say it."""

    message = f"DevLoop could not start. See {os.path.join(paths.home(), LOG_FILE)}."

    print(message)

    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, message, TITLE, 0x10)

        except (OSError, AttributeError):
            pass


def serve(port: int = 0) -> None:
    """The page server in this process, until it is stopped."""

    os.makedirs(paths.home(), exist_ok=True)

    if not port:
        # In the foreground (DEVLOOP_NO_BROWSER=1): its own port file.
        running = running_port()

        if running:
            print(f"DevLoop is already running: http://{HOST}:{running}")
            return

        port = free_port()

        with open(port_file(), "w", encoding="utf-8") as handle:
            handle.write(str(port))

    print(f"DevLoop {version()} — http://{HOST}:{port}", flush=True)
    print(f"Data: {paths.home()}", flush=True)

    # The page's own imports resolve against the code folder.
    os.chdir(paths.ROOT)

    if paths.ROOT not in sys.path:
        sys.path.insert(0, paths.ROOT)

    from streamlit.web import cli

    sys.argv = streamlit_arguments(port)

    sys.exit(cli.main())


def version() -> str:

    from services import build_info

    return build_info.label()


def main(argv: list[str]) -> None:

    if len(argv) >= 3 and argv[1] == "--worker":
        from services import plan_runner

        plan_runner.main(argv[2])
        return

    if len(argv) >= 3 and argv[1] == "--serve":
        serve(int(argv[2]))
        return

    if (os.getenv("DEVLOOP_NO_BROWSER") or "").strip() == "1":
        serve()
        return

    application()


if __name__ == "__main__":

    main(sys.argv)
