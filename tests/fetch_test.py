"""Offline checks for fetching, and for where plans branch from.

A bare repository in a temp folder plays origin, so this
runs with no network:

    python -m tests.fetch_test

The problem it exists for: fetch was forbidden, so a pull
request merged on GitHub never reached the local main, and
the next plan was planned, generated and branched on code
the team had already moved past.
"""

import os
import shutil
import subprocess
import tempfile

from services import plan_branch
from services.git_service import GitError, GitService

failures: list[str] = []


def check(
    label: str,
    actual: object,
    expected: object,
) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


def refused(label: str, call) -> None:

    try:
        call()

    except GitError:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: it was allowed")


def git(path: str, *arguments: str) -> str:

    return subprocess.run(
        ["git", "-C", path, *arguments],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def identity(path: str) -> None:

    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")


def commit(path: str, name: str, content: str) -> str:

    with open(os.path.join(path, name), "w", encoding="utf-8") as h:
        h.write(content)

    git(path, "add", "--", name)
    git(path, "commit", "-m", f"add {name}")

    return git(path, "rev-parse", "HEAD")


folders: list[str] = []


def folder() -> str:

    path = tempfile.mkdtemp()

    folders.append(path)

    return path


try:

    origin = folder()

    git(origin, "init", "--bare", "-b", "main")

    local = folder()

    git(local, "init", "-b", "main")
    identity(local)
    git(local, "remote", "add", "origin", origin)

    commit(local, "README.md", "# one\n")

    git(local, "push", "origin", "main")

    service = GitService(local)

    print("=" * 80)
    print("FETCH IN ONE SHAPE ONLY")
    print("=" * 80)

    service.fetch()

    print("OK   git fetch --quiet origin runs")

    refused(
        "a refspec that would rewrite a local branch",
        lambda: service._run("fetch", "origin", "main:main"),
    )

    refused(
        "a flag outside the allowed set",
        lambda: service._run("fetch", "--prune", "origin"),
    )

    refused(
        "two remotes at once",
        lambda: service._run("fetch", "origin", "upstream"),
    )

    refused(
        "merge-base in any shape but --is-ancestor",
        lambda: service._run("merge-base", "main", "HEAD"),
    )

    refused(
        "pull stays forbidden",
        lambda: service._run("pull"),
    )

    print()
    print("=" * 80)
    print("WHERE A NEW PLAN BRANCHES FROM")
    print("=" * 80)

    check(
        "up to date: from local main",
        service.start_point()[0],
        "main",
    )

    # Somebody merges a pull request on GitHub.
    teammate = folder()

    subprocess.run(
        ["git", "clone", "-q", origin, teammate],
        check=True,
        capture_output=True,
    )

    identity(teammate)

    merged = commit(teammate, "merged.ts", "export const m = 1;\n")

    git(teammate, "push", "origin", "main")

    local_before = git(local, "rev-parse", "main")

    start, note = service.start_point()

    check("behind: from origin/main", start, "origin/main")

    check("and the note says why", "behind" in note, True)

    check(
        "fetch moved no local branch",
        git(local, "rev-parse", "main"),
        local_before,
    )

    check(
        "and touched no file",
        os.path.exists(os.path.join(local, "merged.ts")),
        False,
    )

    entered = plan_branch.enter(
        local,
        plan_branch.name("abcdef12", "Next requirement"),
    )

    check(
        "the plan's branch starts at the merged work",
        git(local, "rev-parse", entered.branch),
        merged,
    )

    check(
        "and its step says where from",
        "origin/main" in entered.note,
        True,
    )

    git(local, "checkout", "-q", "main")

    # Our own scaffolding commit, not pushed, on top of a
    # main that is behind: the two have diverged.
    commit(local, "package.json", "{}\n")

    start, note = service.start_point()

    check("diverged: from origin/main", start, "origin/main")

    check("and the note warns", "diverged" in note, True)

    # Bring local main level, then add a local commit: ahead.
    git(local, "checkout", "-q", "-B", "main", "origin/main")

    commit(local, "package.json", "{}\n")

    check(
        "ahead with our own commits: from local main",
        service.start_point()[0],
        "main",
    )

    print()
    print("=" * 80)
    print("WITHOUT A REMOTE, OR WITHOUT A CONNECTION")
    print("=" * 80)

    alone = folder()

    git(alone, "init", "-b", "main")
    identity(alone)
    commit(alone, "README.md", "# alone\n")

    check(
        "no remote: local main, nothing to say",
        GitService(alone).start_point(),
        ("main", ""),
    )

    git(
        local,
        "remote",
        "set-url",
        "origin",
        os.path.join(folder(), "does-not-exist"),
    )

    start, note = service.start_point()

    check("unreachable: local main", start, "main")

    check("and the note says so", "not reachable" in note, True)

finally:
    for path in folders:
        shutil.rmtree(path, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL FETCH CHECKS PASSED")
print("=" * 80)
