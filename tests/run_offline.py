"""Runs every offline suite and says which failed.

No model, no network, no token: the four suites that call
a real model are left out. From the project root:

    python tests/run_offline.py

Each suite is a plain script, run in its own process so
one that patches a module cannot leak into the next. The
exit code is non-zero when any suite fails, which is what
CI reads.
"""

import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# They spend tokens, or need a local Ollama.
LIVE = frozenset(
    {
        "architect_test",
        "langgraph_test",
        "ollama_test",
        "workflow_test",
    }
)

# How much of a failing suite's output to show.
TAIL_LINES = 40


def suites() -> list[str]:

    folder = os.path.join(ROOT, "tests")

    return sorted(
        name[:-3]
        for name in os.listdir(folder)
        if name.endswith("_test.py") and name[:-3] not in LIVE
    )


def main() -> int:

    environment = {
        **os.environ,
        "PYTHONPATH": ROOT,
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }

    failed: list[str] = []

    started = time.monotonic()

    for name in suites():

        began = time.monotonic()

        result = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tests", f"{name}.py")],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        took = time.monotonic() - began

        if result.returncode == 0:
            print(f"PASS {name} ({took:.1f}s)")
            continue

        failed.append(name)

        print(f"FAIL {name} ({took:.1f}s)")

        output = (result.stdout + result.stderr).splitlines()

        for line in output[-TAIL_LINES:]:
            print(f"     {line}")

    total = len(suites())

    print()
    print(
        f"{total - len(failed)}/{total} suites passed "
        f"in {time.monotonic() - started:.0f}s"
        + (f"; failed: {', '.join(failed)}" if failed else "")
    )

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
