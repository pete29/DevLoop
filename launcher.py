"""DevLoop's entry point in the exe: the page on this computer only.

    DevLoop.exe                 starts the page and opens it
    DevLoop.exe --worker <id>   one background run (started by the page)

The page listens on 127.0.0.1 alone, never on the network: it
holds the API keys and can write to any folder. A second start
while one is running opens the running one rather than a
second server on the same database. The console window that
stays open is DevLoop's log; closing it stops DevLoop.

From source the same file works too: python launcher.py.
"""

import os
import socket
import subprocess
import sys
import webbrowser

from config import paths

HOST = "127.0.0.1"

# The port Streamlit is used to, when it is free.
PREFERRED_PORT = 8501

PORT_FILE = "launcher.port"


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


def open_page(url: str) -> None:
    """The page in a window of its own where Edge exists, else a browser tab."""

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
        # Source files never change inside the exe.
        "--server.fileWatcherType=none",
    ]


def serve() -> None:

    os.makedirs(paths.home(), exist_ok=True)

    running = running_port()

    if running:
        print(f"DevLoop is already running: http://{HOST}:{running}")
        open_page(f"http://{HOST}:{running}")
        return

    port = free_port()

    with open(port_file(), "w", encoding="utf-8") as handle:
        handle.write(str(port))

    url = f"http://{HOST}:{port}"

    print(f"DevLoop {version()} — {url}")
    print(f"Data: {paths.home()}")
    print("Close this window to stop DevLoop.")

    # Streamlit blocks; the page opens once it can answer.
    import threading

    def open_when_ready() -> None:
        for _ in range(120):
            if answering(port):
                open_page(url)
                return
            threading.Event().wait(0.5)

    threading.Thread(target=open_when_ready, daemon=True).start()

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

    serve()


if __name__ == "__main__":

    main(sys.argv)
