"""Offline checks for Step 0, the environment a plan needs.

Real git in throwaway folders; the npm install is faked by
creating what it would leave behind, so this runs with no
network:

    python -m tests.environment_test
"""

import os
import shutil
import subprocess
import tempfile

from agents.git_agent import GitAgent
from models.file_type import FileType
from models.generated_file import GeneratedFile
from models.task import Task
from models.task_status import TaskStatus
from services.environment_step import (
    LOCK_FILE,
    assess,
    commit_scaffolding,
    write_scaffolding,
)
from services.git_service import GitError
from workflows.review_decision import ReviewDecision

failures: list[str] = []

SCAFFOLDING = [
    "package.json",
    "tsconfig.json",
    "vitest.config.ts",
    ".gitignore",
]


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


def git(path: str, *arguments: str) -> str:

    return subprocess.run(
        ["git", "-C", path, *arguments],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def repository() -> str:
    """A git repository with one commit on main."""

    path = tempfile.mkdtemp()

    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")

    with open(
        os.path.join(path, "README.md"), "w", encoding="utf-8"
    ) as handle:
        handle.write("# test\n")

    git(path, "add", "--", "README.md")
    git(path, "commit", "-m", "initial")

    return path


def fake_install(path: str) -> None:
    """What npm install leaves behind, minus the network."""

    os.makedirs(
        os.path.join(path, "node_modules", "typescript", "lib")
    )

    open(
        os.path.join(
            path, "node_modules", "typescript", "lib", "tsc.js"
        ),
        "w",
    ).close()

    os.makedirs(os.path.join(path, "node_modules", "vitest"))

    with open(
        os.path.join(path, LOCK_FILE), "w", encoding="utf-8"
    ) as handle:
        handle.write("{}\n")


folders: list[str] = []

try:

    print("=" * 80)
    print("A FOLDER WITHOUT GIT IS NOT READY")
    print("=" * 80)

    bare = tempfile.mkdtemp()

    folders.append(bare)

    step = assess(bare)

    check("git is reported missing", step.git, False)

    check("so the step is not ready", step.ready, False)

    check(
        "and all the scaffolding is missing",
        step.missing,
        SCAFFOLDING,
    )

    print()
    print("=" * 80)
    print("A REPOSITORY WHERE GIT DOES NOT KNOW WHO COMMITS")
    print("=" * 80)

    from services.git_service import GitService

    anonymous = tempfile.mkdtemp()

    folders.append(anonymous)

    git(anonymous, "init", "-b", "main")

    # This machine's own identity, if it has one, is hidden.
    saved = {name: os.environ.get(name) for name in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_NOSYSTEM")}

    os.environ["GIT_CONFIG_GLOBAL"] = os.path.join(anonymous, "no-global-config")

    os.environ["GIT_CONFIG_NOSYSTEM"] = "1"

    try:
        step = assess(anonymous)

        check("it is reported", step.identity_missing, True)

        check("so the step is not ready", step.ready, False)

        GitService(anonymous).set_identity("Ada Lovelace", "ada@example.com")

        check("once given, for this repository", GitService(anonymous).identity(), ("Ada Lovelace", "ada@example.com"))

        check("it is no longer missing", assess(anonymous).identity_missing, False)

    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value

    for shape in (
        ("config", "--global", "user.name", "x"),
        ("config", "core.hooksPath", "x"),
        ("config", "--local", "user.name", "a\nb"),
        ("config", "--get", "remote.origin.url"),
    ):
        refused = False
        try:
            GitService(anonymous)._run(*shape)
        except GitError:
            refused = True
        check(f"git {' '.join(shape)!r} is refused", refused, True)

    print()
    print("=" * 80)
    print("AN EMPTY REPOSITORY, STEP BY STEP")
    print("=" * 80)

    path = repository()

    folders.append(path)

    step = assess(path)

    check("git is there", step.git, True)

    check("the base branch is found", step.base_branch, "main")

    check("nothing to commit yet", step.uncommitted, [])

    check("dependencies are missing", step.dependencies_missing, True)

    check("not ready", step.ready, False)

    created = write_scaffolding(path)

    check("the scaffolding is written", created, SCAFFOLDING)

    step = assess(path)

    check("then nothing is missing", step.missing, [])

    check(
        "but none of it is in git",
        step.uncommitted,
        SCAFFOLDING,
    )

    fake_install(path)

    step = assess(path)

    check(
        "after the install, dependencies are there",
        step.dependencies_missing,
        False,
    )

    check(
        "and the lock file waits to be committed too",
        LOCK_FILE in step.uncommitted,
        True,
    )

    check(
        "node_modules is not offered for a commit",
        any("node_modules" in item for item in step.uncommitted),
        False,
    )

    print()
    print("=" * 80)
    print("THE SCAFFOLDING IS COMMITTED ON THE BASE BRANCH")
    print("=" * 80)

    # Added to the index by hand, never committed: tracked,
    # yet on no branch. It counted as committed, and went
    # into the first task's commit.
    git(path, "add", *SCAFFOLDING)

    check(
        "staged is still not committed",
        sorted(assess(path).uncommitted),
        sorted(SCAFFOLDING + [LOCK_FILE]),
    )

    # Left on a task branch by an earlier run.
    git(path, "checkout", "-b", "devloop/earlier-task")

    commit_hash = commit_scaffolding(path)

    check("a commit was made", len(commit_hash) >= 7, True)

    check(
        "on main, not on the branch that was checked out",
        git(path, "branch", "--show-current").strip(),
        "main",
    )

    check(
        "with exactly the scaffolding and the lock file",
        sorted(
            git(
                path,
                "show",
                "--name-only",
                "--format=",
                "HEAD",
            ).split()
        ),
        sorted(SCAFFOLDING + [LOCK_FILE]),
    )

    check(
        "and the earlier branch does not have it",
        "package.json"
        in git(path, "ls-tree", "--name-only", "devloop/earlier-task"),
        False,
    )

    check("now the step is ready", assess(path).ready, True)

    try:
        commit_scaffolding(path)
        failures.append("a second commit is refused")
        print("FAIL a second commit is refused")
    except GitError:
        print("OK   a second commit is refused")

    print()
    print("=" * 80)
    print("A TASK THAT WROTE ITS OWN SCAFFOLDING COMMITS IT")
    print("=" * 80)

    solo = repository()

    folders.append(solo)

    written = write_scaffolding(solo)

    os.makedirs(os.path.join(solo, "src"))

    with open(
        os.path.join(solo, "src", "a.ts"), "w", encoding="utf-8"
    ) as handle:
        handle.write("export const a = 1;\n")

    operation = GitAgent.execute(
        Task(
            repository_path=solo,
            description="Create a.",
            architecture_score=95,
            recommendation=ReviewDecision.APPROVE,
            generated_files=[
                GeneratedFile("src/a.ts", FileType.SOURCE)
            ],
            environment=written,
            status=TaskStatus.APPROVED,
        )
    )

    committed = git(
        solo,
        "show",
        "--name-only",
        "--format=",
        operation.commit_hash,
    ).split()

    check(
        "the task commit holds the code and the scaffolding",
        sorted(committed),
        sorted(["src/a.ts", *SCAFFOLDING]),
    )

finally:
    for folder in folders:
        shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL ENVIRONMENT CHECKS PASSED")
print("=" * 80)
