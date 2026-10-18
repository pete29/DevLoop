"""Offline checks: the exe's entry point and where its data lives.

Nothing is started and no port is taken for long:

    python -m tests.launcher_test
"""

import os
import socket
import sys
import tempfile

import launcher
from config import paths

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


print("=" * 80)
print("WHERE THE DATA LIVES")
print("=" * 80)

saved = {name: os.environ.get(name) for name in ("DEVLOOP_HOME", "LOCALAPPDATA")}

os.environ.pop("DEVLOOP_HOME", None)

check("from source, the project folder, as always", paths.home(), paths.ROOT)

sys.frozen = True

os.environ["LOCALAPPDATA"] = os.path.join("C:\\", "Users", "me", "AppData", "Local")

check(
    "in the exe, %LOCALAPPDATA%\\DevLoop: the code folder is temporary",
    paths.home(),
    os.path.join(os.environ["LOCALAPPDATA"], "DevLoop"),
)

check(".env sits beside the database", paths.env_path(), os.path.join(paths.home(), ".env"))

os.environ["DEVLOOP_HOME"] = os.path.join("D:\\", "devloop-data")

check("DEVLOOP_HOME overrides both", paths.home(), os.path.join("D:\\", "devloop-data"))

del sys.frozen

for name, value in saved.items():
    if value is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = value

print()
print("=" * 80)
print("THE PAGE IS FOR THIS COMPUTER ONLY")
print("=" * 80)

arguments = launcher.streamlit_arguments(8765)

check("bound to 127.0.0.1, never the network", "--server.address=127.0.0.1" in arguments, True)

check("on the port chosen", "--server.port=8765" in arguments, True)

check("it runs app.py from the code folder", arguments[2], os.path.join(paths.ROOT, "app.py"))

print()
print("=" * 80)
print("A SECOND START OPENS THE RUNNING ONE")
print("=" * 80)

os.environ["DEVLOOP_HOME"] = tempfile.mkdtemp()

check("no port file: nothing is running", launcher.running_port(), 0)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:

    server.bind(("127.0.0.1", 0))

    server.listen()

    port = server.getsockname()[1]

    with open(launcher.port_file(), "w", encoding="utf-8") as handle:
        handle.write(str(port))

    check("a port that answers is the running DevLoop", launcher.running_port(), port)

check("once it stopped answering, it is not", launcher.running_port(), 0)

with open(launcher.port_file(), "w", encoding="utf-8") as handle:
    handle.write("not a port")

check("a damaged port file is ignored", launcher.running_port(), 0)

print()
print("=" * 80)
print("THE SAME EXE RUNS THE BACKGROUND WORKER")
print("=" * 80)

from services import plan_runner  # noqa: E402

started: list[str] = []

plan_runner.main = lambda run_id: started.append(run_id)

served: list[int] = []

launcher.serve = lambda port=0: served.append(port)

windows: list[bool] = []

launcher.application = lambda: windows.append(True)

os.environ.pop("DEVLOOP_NO_BROWSER", None)

launcher.main(["DevLoop.exe", "--worker", "run-1"])

check("--worker runs that run, and nothing else", (started, served, windows), (["run-1"], [], []))

launcher.main(["DevLoop.exe", "--serve", "8600"])

check("--serve runs the page server on the port the window chose", served, [8600])

launcher.main(["DevLoop.exe"])

check("with no arguments, the application window", windows, [True])

os.environ["DEVLOOP_NO_BROWSER"] = "1"

launcher.main(["DevLoop.exe"])

check("DEVLOOP_NO_BROWSER=1 serves in the foreground instead, for a smoke test", (served, windows), ([8600, 0], [True]))

os.environ.pop("DEVLOOP_NO_BROWSER", None)

print()
print("=" * 80)
print("THE WINDOW STARTS ITS SERVER AS ITSELF")
print("=" * 80)

check(
    "from source, launcher.py again",
    launcher.self_command("--serve", "8600")[1:],
    [os.path.abspath(launcher.__file__), "--serve", "8600"],
)

sys.frozen = True

check("in the exe, the exe again", launcher.self_command("--serve", "8600"), [sys.executable, "--serve", "8600"])

del sys.frozen

check("a page that never answers is given up on", launcher.wait_for(1, seconds=0.5), False)

print()
print("=" * 80)
print("WEBVIEW2 MUST BE THERE, NOT ONLY REGISTERED")
print("=" * 80)

runtime = tempfile.mkdtemp()

check(
    "registered but its folder empty: not ready, so no blank window (#82)",
    launcher.webview2_ready(["151.0.4129.78"], [runtime]),
    False,
)

os.makedirs(os.path.join(runtime, "151.0.4129.78"))

with open(os.path.join(runtime, "151.0.4129.78", "msedgewebview2.exe"), "w") as handle:
    handle.write("")

check("registered and on disk: ready", launcher.webview2_ready(["151.0.4129.78"], [runtime]), True)

check("not registered at all: not ready", launcher.webview2_ready([], [runtime]), False)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL LAUNCHER CHECKS PASSED")
print("=" * 80)
