"""Offline checks for the version and the commit shown on the page.

    python -m tests.version_test
"""

import os
import re
import shutil
import tempfile

from config.version import STAGE, VERSION
from services import build_info

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


def write(root: str, path: str, content: str) -> None:

    target = os.path.join(root, *path.split("/"))

    os.makedirs(os.path.dirname(target), exist_ok=True)

    with open(target, "w", encoding="utf-8") as handle:
        handle.write(content)


HASH = "4fd5c5f0123456789abcdef0123456789abcdef0"

folder = tempfile.mkdtemp()

try:

    print("=" * 80)
    print("THE VERSION")
    print("=" * 80)

    check("is MAJOR.MINOR.PATCH", bool(re.fullmatch(r"\d+\.\d+\.\d+", VERSION)), True)

    check("its stage is a known one", STAGE in ("alpha", "beta", "rc", ""), True)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    with open(os.path.join(root, "CHANGELOG.md"), encoding="utf-8") as handle:
        changelog = handle.read()

    check("and the changelog has an entry for it", f"## {VERSION}" in changelog, True)

    print()
    print("=" * 80)
    print("THE COMMIT, READ FROM .git")
    print("=" * 80)

    loose = os.path.join(folder, "loose")

    write(loose, ".git/HEAD", "ref: refs/heads/main\n")
    write(loose, ".git/refs/heads/main", HASH + "\n")

    check("a branch's own file", build_info.commit(loose), "4fd5c5f")

    packed = os.path.join(folder, "packed")

    write(packed, ".git/HEAD", "ref: refs/heads/main\n")
    write(packed, ".git/packed-refs", f"# pack-refs with: peeled\n{HASH} refs/heads/main\n")

    check("a branch packed by git gc", build_info.commit(packed), "4fd5c5f")

    detached = os.path.join(folder, "detached")

    write(detached, ".git/HEAD", HASH + "\n")

    check("a detached HEAD", build_info.commit(detached), "4fd5c5f")

    check("no repository, no commit", build_info.commit(os.path.join(folder, "none")), "")

    check("the label puts them together", build_info.label(loose), f"v{VERSION}" + (f" {STAGE}" if STAGE else "") + " · 4fd5c5f")

    check(
        "and leaves the commit out when there is none",
        build_info.label(os.path.join(folder, "none")),
        f"v{VERSION}" + (f" {STAGE}" if STAGE else ""),
    )

finally:
    shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL VERSION CHECKS PASSED")
print("=" * 80)
