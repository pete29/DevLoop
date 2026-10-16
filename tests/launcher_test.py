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

served: list[bool] = []

launcher.serve = lambda: served.append(True)

launcher.main(["DevLoop.exe", "--worker", "run-1"])

check("--worker runs that run, and no page", (started, served), (["run-1"], []))

launcher.main(["DevLoop.exe"])

check("without it, the page", served, [True])

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL LAUNCHER CHECKS PASSED")
print("=" * 80)
