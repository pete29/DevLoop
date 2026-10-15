"""Runs the offline tests under coverage and reports what they reach.

    python tests/coverage.py            the summary, and coverage-html/
    python tests/coverage.py -m unit    any pytest arguments after it

Every Python process the tests start is measured -- each suite
runs in its own, and some start a background worker -- and the
data is combined before the report. CI prints the summary.

The full-path end-to-end test is left out of this run: it
renders the page inside pytest's own process, and under
coverage that render fails to import numpy ("cannot load
module more than once per process"). It still runs, unmeasured,
in every plain `pytest`; see issue #42.
"""

import os
import shutil
import subprocess
import sys

# Deselected here only; see the docstring.
UNMEASURED = "not full_path"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RCFILE = os.path.join(ROOT, ".coveragerc")

DATA = os.path.join(ROOT, ".coverage-data")


def coverage(*arguments: str) -> int:

    return subprocess.call([sys.executable, "-m", "coverage", *arguments, f"--rcfile={RCFILE}"], cwd=ROOT)


def main() -> int:

    shutil.rmtree(DATA, ignore_errors=True)

    os.makedirs(DATA)

    tested = subprocess.call(
        [
            sys.executable, "-m", "coverage", "run", f"--rcfile={RCFILE}", "-m", "pytest",
            "-k", UNMEASURED,
            *(sys.argv[1:] or ["-q"]),
        ],
        cwd=ROOT,
        env={**os.environ, "PYTHONPATH": ROOT},
    )

    coverage("combine", "--quiet")

    coverage("report")

    coverage("html", "--quiet")

    print(f"\nPer file, line by line: {os.path.join(ROOT, 'coverage-html', 'index.html')}")

    return tested


if __name__ == "__main__":
    sys.exit(main())
