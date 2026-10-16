"""What DevLoop needs before its first task, and whether it is there.

The exe is meant for someone who has never set DevLoop up:
git, Node.js and an Anthropic key are needed before anything
can run, and finding that out from a failed run costs money.
"""

import os
import re
import shutil
import subprocess
from dataclasses import dataclass

# The oldest Node.js the toolchain DevLoop installs supports.
MIN_NODE_MAJOR = 18

VERSION = re.compile(r"(\d+)\.(\d+)")


@dataclass(frozen=True)
class Check:
    """One thing DevLoop needs, and what was found."""

    key: str

    ok: bool

    required: bool

    # A version, or why it is missing.
    detail: str = ""

    # Where to get it.
    link: str = ""


def version_of(program: str) -> str:
    """`<program> --version`'s first line, or "" if it cannot run."""

    found = shutil.which(program)

    if not found:
        return ""

    try:
        completed = subprocess.run(
            [found, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    except (OSError, subprocess.SubprocessError):
        return ""

    lines = (completed.stdout or completed.stderr or "").strip().splitlines()

    return lines[0].strip() if lines else ""


def git_check(found: str) -> Check:

    return Check(
        "git",
        bool(found),
        True,
        found or "not found on PATH",
        "https://git-scm.com/downloads",
    )


def node_check(found: str) -> Check:

    match = VERSION.search(found)

    major = int(match.group(1)) if match else 0

    if not found:
        detail = "not found on PATH"

    elif major < MIN_NODE_MAJOR:
        detail = f"{found}: {MIN_NODE_MAJOR} or newer is needed"

    else:
        detail = found

    return Check("node", major >= MIN_NODE_MAJOR, True, detail, "https://nodejs.org/en/download")


def key_check(name: str, required: bool, link: str) -> Check:

    value = (os.getenv(name) or "").strip()

    return Check(name, bool(value), required, "set" if value else "not set", link)


def checks() -> list[Check]:
    """Everything DevLoop needs, in the order to set it up."""

    return [
        git_check(version_of("git")),
        node_check(version_of("node")),
        key_check("ANTHROPIC_API_KEY", True, "https://console.anthropic.com/settings/keys"),
        key_check("GITHUB_PAT", False, "https://github.com/settings/personal-access-tokens"),
    ]


def ready(found: list[Check]) -> bool:
    """Whether every required check passed."""

    return all(check.ok for check in found if check.required)
