"""Offline check: rejecting a whole plan in one click.

The real page, headless, with a real git repository in a
throwaway folder; nothing calls a model or GitHub:

    python -m tests.reject_plan_test
"""

import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

folder = tempfile.mkdtemp()

os.environ["DEVLOOP_DATABASE"] = os.path.join(folder, "reject.db")

from streamlit.testing.v1 import AppTest  # noqa: E402

from database.plan_repository import PlanRepository  # noqa: E402
from database.repository_repository import RepositoryRepository  # noqa: E402
from database.task_repository import TaskRepository  # noqa: E402
from models.file_type import FileType  # noqa: E402
from models.generated_file import GeneratedFile  # noqa: E402
from models.plan import Plan  # noqa: E402
from models.repository import Repository  # noqa: E402
from models.task import Task  # noqa: E402
from models.task_breakdown import TaskBreakdown  # noqa: E402
from models.task_execution import ExecutionStatus, TaskExecution  # noqa: E402
from models.task_status import TaskStatus  # noqa: E402
from services import plan_branch  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


def git(*args: str) -> None:

    subprocess.run(["git", "-C", root, *args], capture_output=True, check=True)


def write(path: str, content: str) -> None:

    target = os.path.join(root, path)

    os.makedirs(os.path.dirname(target) or root, exist_ok=True)

    with open(target, "w", encoding="utf-8") as handle:
        handle.write(content)


try:

    root = os.path.join(folder, "repo")

    os.makedirs(root)

    git("init", "--quiet", "--initial-branch=main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "Test")

    write("package.json", "{}")

    git("add", "package.json")
    git("commit", "--quiet", "-m", "start")

    repository = Repository(name="repo", path=root)

    RepositoryRepository().save(repository)

    plan = Plan(
        repository_id=repository.id,
        epic="Dates",
        tasks=[
            TaskBreakdown(id=1, title="types"),
            TaskBreakdown(id=2, title="days", dependencies=[1]),
        ],
    )

    PlanRepository().save(plan)

    branch = plan_branch.of(plan)

    git("checkout", "--quiet", "-b", branch)

    # Task 1 wrote its file; task 2 wrote one, rewrote task
    # 1's, and changed a file git knows.
    write("src/types.ts", "export type A = string;")
    write("src/days.ts", "export const d = 1;")
    write("types.js", "export {};")
    write("package.json", '{"broken": true}')

    started = datetime.now(timezone.utc)

    first = Task(
        repository_id=repository.id,
        repository_path=root,
        description="types",
        status=TaskStatus.WAITING_FOR_APPROVAL,
        branch=branch,
        generated_files=[GeneratedFile("src/types.ts", FileType.SOURCE, "")],
        created_files=["src/types.ts"],
        created_at=started.isoformat(),
    )

    second = Task(
        repository_id=repository.id,
        repository_path=root,
        description="days",
        status=TaskStatus.WAITING_FOR_APPROVAL,
        branch=branch,
        generated_files=[
            GeneratedFile("src/days.ts", FileType.SOURCE, ""),
            GeneratedFile("src/types.ts", FileType.SOURCE, ""),
            GeneratedFile("types.js", FileType.SOURCE, ""),
            GeneratedFile("package.json", FileType.SOURCE, ""),
        ],
        created_files=["src/days.ts", "types.js"],
        created_at=(started + timedelta(seconds=1)).isoformat(),
    )

    for record in (first, second):
        TaskRepository().save(record)

    for item, record in ((1, first), (2, second)):
        plan.record(
            TaskExecution(
                task_id=item,
                status=ExecutionStatus.COMPLETED,
                started_at=record.created_at,
                completed_at=record.created_at,
                task_record_id=record.id,
            )
        )

    PlanRepository().update_progress(plan)

    app = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")

    at = AppTest.from_file(app, default_timeout=60)

    at.run()

    at.session_state.repository_id = repository.id

    at.session_state.plan = PlanRepository().get_by_id(plan.id)

    at.run()

    check("the page did not fail", [e.value for e in at.exception], [])

    reject = [item for item in at.button if item.key == f"reject-all-{plan.id}"]

    check("the plan offers to reject both tasks, after a confirmation", [item.disabled for item in reject], [True])

    at.checkbox(key=f"reject-all-sure-{plan.id}").check().run()

    [item for item in at.button if item.key == f"reject-all-{plan.id}"][0].click().run()

    check("the page did not fail", [e.value for e in at.exception], [])

    check(
        "both are rejected",
        [TaskRepository().get_by_id(record.id).status for record in (first, second)],
        [TaskStatus.REJECTED, TaskStatus.REJECTED],
    )

    check(
        "every file the tasks created is gone",
        [os.path.exists(os.path.join(root, path)) for path in ("src/types.ts", "src/days.ts", "types.js")],
        [False, False, False],
    )

    with open(os.path.join(root, "package.json"), encoding="utf-8") as handle:
        check("the file git knows is restored", handle.read(), "{}")

    check(
        "and the plan can run both again",
        [item.id for item in PlanRepository().get_by_id(plan.id).remaining],
        [1, 2],
    )

    check(
        "nothing is left to reject",
        [item.key for item in at.button if item.key == f"reject-all-{plan.id}"],
        [],
    )

finally:
    shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL REJECT PLAN CHECKS PASSED")
print("=" * 80)
