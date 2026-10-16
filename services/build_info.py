"""The version and the commit the running code came from.

The commit is read from .git's own files rather than by
running git: the label is drawn on every page load, and a
copy of DevLoop without git still has a version to show.
"""

import os

from config.version import STAGE, VERSION

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def commit(root: str = ROOT) -> str:
    """The short hash of HEAD, or "" when there is no repository."""

    git = os.path.join(root, ".git")

    try:
        with open(os.path.join(git, "HEAD"), encoding="utf-8") as handle:
            head = handle.read().strip()

        if not head.startswith("ref: "):
            return head[:7]

        ref = head[5:]

        loose = os.path.join(git, *ref.split("/"))

        if os.path.isfile(loose):
            with open(loose, encoding="utf-8") as handle:
                return handle.read().strip()[:7]

        # After git gc a branch lives only in packed-refs.
        with open(os.path.join(git, "packed-refs"), encoding="utf-8") as handle:
            for line in handle:
                parts = line.split()
                if len(parts) == 2 and parts[1] == ref:
                    return parts[0][:7]

    except OSError:
        return ""

    return ""


def label(root: str = ROOT) -> str:
    """"v0.9.0 alpha · 4fd5c5f", as much of it as is known."""

    text = f"v{VERSION}" + (f" {STAGE}" if STAGE else "")

    found = commit(root) or built_commit()

    return f"{text} · {found}" if found else text


def built_commit() -> str:
    """The commit packaging/build_exe.py wrote into the exe, or ""."""

    try:
        from config.build_commit import COMMIT

    except ImportError:
        return ""

    return COMMIT
