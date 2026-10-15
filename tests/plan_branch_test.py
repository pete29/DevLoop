"""Offline checks for one branch per plan, and for rejecting.

Real git in throwaway folders, no model:

    python -m tests.plan_branch_test

The bug this exists for: the second task of a plan was
generated beside the first task's files, then committed
onto a fresh branch from main that did not have them.
"""

import os
import shutil
import subprocess
import tempfile

from agents.git_agent import GitAgent
from database.task_repository import TaskRepository
from models.file_type import FileType
from models.generated_file import GeneratedFile
from models.task import Task
from models.task_status import TaskStatus
from services import plan_branch
from services.git_service import GitError, is_valid_branch
from services.task_rollback import roll_back
from workflows.review_decision import ReviewDecision

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


def refused(label: str, call, error=GitError) -> None:

    try:
        call()

    except error:
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
    ).stdout


def write(root: str, relative: str, content: str) -> None:

    full = os.path.join(root, *relative.split("/"))

    os.makedirs(os.path.dirname(full), exist_ok=True)

    with open(full, "w", encoding="utf-8") as handle:
        handle.write(content)


def read(root: str, relative: str) -> str:

    with open(
        os.path.join(root, *relative.split("/")),
        encoding="utf-8",
    ) as handle:
        return handle.read()


def repository() -> str:

    path = tempfile.mkdtemp()

    git(path, "init", "-b", "main")
    git(path, "config", "user.email", "test@example.com")
    git(path, "config", "user.name", "Test")

    write(path, "README.md", "# test\n")

    git(path, "add", "--", "README.md")
    git(path, "commit", "-m", "initial")

    return path


def task(root: str, branch: str, created: list[str], *paths):

    return Task(
        repository_path=root,
        description=f"Create {' '.join(paths)}.",
        architecture_score=95,
        recommendation=ReviewDecision.APPROVE,
        generated_files=[
            GeneratedFile(path, FileType.SOURCE)
            for path in paths
        ],
        created_files=created,
        branch=branch,
        status=TaskStatus.APPROVED,
    )


folders: list[str] = []

try:

    print("=" * 80)
    print("THE PLAN'S BRANCH NAME")
    print("=" * 80)

    named = plan_branch.name(
        "abcdef12-3456",
        "Walidator haseł dla użytkowników panelu admina\nopis",
    )

    check(
        "readable, accents folded, first line only",
        named,
        "feature/plan-abcdef12-walidator-hasel-dla-uzytkownikow",
    )

    check("and valid for git", is_valid_branch(named), True)

    check(
        "an empty epic still names a branch",
        plan_branch.name("abcdef12", ""),
        "feature/plan-abcdef12",
    )

    print()
    print("=" * 80)
    print("TASKS OF ONE PLAN SHARE ONE BRANCH")
    print("=" * 80)

    root = repository()

    folders.append(root)

    branch = plan_branch.name("abcdef12", "Walidator")

    check(
        "the branch is created from main before any work",
        plan_branch.enter(root, branch).branch,
        branch,
    )

    check(
        "and checked out",
        git(root, "branch", "--show-current").strip(),
        branch,
    )

    check(
        "entering again changes nothing",
        plan_branch.enter(root, branch),
        plan_branch.Entered(branch),
    )

    # Task 1 writes a, task 2 imports it -- both generated
    # before either is approved, as a run-all does.
    write(root, "src/a.ts", "export const a = 1;\n")

    first = task(root, branch, ["src/a.ts"], "src/a.ts")

    write(
        root,
        "src/b.ts",
        "import { a } from './a';\nexport const b = a;\n",
    )

    second = task(root, branch, ["src/b.ts"], "src/b.ts")

    refused(
        "the later task cannot be committed first",
        lambda: GitAgent.execute(second, [first, second]),
    )

    one = GitAgent.execute(first, [first, second])

    first.git_operation = one

    check("the first commits onto the plan's branch", one.branch_name, branch)

    two = GitAgent.execute(second, [first, second])

    check("then the second, onto the same branch", two.branch_name, branch)

    check(
        "which holds both tasks' files",
        sorted(
            git(
                root, "ls-tree", "-r", "--name-only", branch
            ).split()
        ),
        ["README.md", "src/a.ts", "src/b.ts"],
    )

    check(
        "and main is untouched",
        git(root, "ls-tree", "-r", "--name-only", "main").split(),
        ["README.md"],
    )

    rejected = task(root, branch, [], "src/x.ts")

    rejected.status = TaskStatus.REJECTED

    later = task(root, branch, [], "src/y.ts")

    check(
        "a rejected earlier task does not hold up a later one",
        GitAgent.unresolved_before(later, [rejected, later]),
        [],
    )

    check(
        "a task outside a plan is never held up",
        GitAgent.unresolved_before(
            task(root, "", [], "src/z.ts"),
            [first, second],
        ),
        [],
    )

    print()
    print("=" * 80)
    print("A BLOCKED SWITCH STOPS THE TASK BEFORE IT RUNS")
    print("=" * 80)

    blocked = repository()

    folders.append(blocked)

    git(blocked, "checkout", "-b", "other")

    write(blocked, "README.md", "# other\n")

    git(blocked, "commit", "-am", "other readme")

    # An uncommitted change to a file that differs between
    # the branches: git refuses to switch over it.
    write(blocked, "README.md", "# uncommitted\n")

    refused(
        "the plan's branch is not created from the wrong place",
        lambda: plan_branch.enter(
            blocked,
            plan_branch.name("12345678", "x"),
        ),
    )

    check(
        "and nothing was switched",
        git(blocked, "branch", "--show-current").strip(),
        "other",
    )

    print()
    print("=" * 80)
    print("REJECTING UNDOES THE TASK'S FILES, AND ONLY THOSE")
    print("=" * 80)

    # On the plan's branch: a.ts is committed, b.ts too.
    write(root, "src/a.ts", "export const a = 999;\n")

    write(root, "src/c.ts", "export const c = 3;\n")

    write(root, "notes.txt", "somebody's own file\n")

    third = task(
        root,
        branch,
        ["src/c.ts"],
        "src/a.ts",
        "src/c.ts",
        "notes.txt",
    )

    undone = roll_back(third)

    check(
        "the file it created is deleted",
        (undone.removed, os.path.exists(os.path.join(root, "src", "c.ts"))),
        (["src/c.ts"], False),
    )

    check(
        "the tracked file it changed is restored from git",
        (undone.restored, read(root, "src/a.ts")),
        (["src/a.ts"], "export const a = 1;\n"),
    )

    check(
        "a file it neither created nor git knows is kept",
        (undone.kept, read(root, "notes.txt")),
        (["notes.txt"], "somebody's own file\n"),
    )

    git(root, "checkout", "main")

    refused(
        "rejecting on another branch is refused",
        lambda: roll_back(third),
        ValueError,
    )

    print()
    print("=" * 80)
    print("THE BRANCH AND THE CREATED FILES ARE SAVED")
    print("=" * 80)

    database = os.path.join(tempfile.mkdtemp(), "tasks.db")

    folders.append(os.path.dirname(database))

    store = TaskRepository(database)

    store.save(third)

    loaded = store.get_by_id(third.id)

    check(
        "both come back",
        (loaded.branch, loaded.created_files),
        (branch, ["src/c.ts"]),
    )

    store.connection.close()

finally:
    for folder in folders:
        shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL PLAN BRANCH CHECKS PASSED")
print("=" * 80)
