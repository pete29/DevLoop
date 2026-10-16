"""Offline check: a running plan shows which task runs and which wait.

The real page, headless, against a throwaway database. Every
task had failed in an earlier run; a new run is on task 2:

    python -m tests.run_view_test
"""

import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone

folder = tempfile.mkdtemp()

os.environ["DEVLOOP_DATABASE"] = os.path.join(folder, "run-view.db")

# A password in the developer's .env would stop the page at
# the sign-in screen; set, even empty, .env does not override it.
os.environ["DEVLOOP_PASSWORD_HASH"] = ""

from streamlit.testing.v1 import AppTest  # noqa: E402

from database.plan_repository import PlanRepository  # noqa: E402
from database.repository_repository import RepositoryRepository  # noqa: E402
from database.run_repository import RunRepository  # noqa: E402
from models.plan import Plan  # noqa: E402
from models.plan_run import PlanRun, RunStatus  # noqa: E402
from models.repository import Repository  # noqa: E402
from models.task_breakdown import TaskBreakdown  # noqa: E402
from models.task_execution import ExecutionStatus, TaskExecution  # noqa: E402
from services import plan_runner  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


def stamp(minutes_ago: float) -> str:

    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


try:

    root = os.path.join(folder, "repo")

    os.makedirs(root)

    repository = Repository(name="repo", path=root)

    RepositoryRepository().save(repository)

    plan = Plan(
        repository_id=repository.id,
        epic="Dates",
        tasks=[
            TaskBreakdown(id=1, title="types"),
            TaskBreakdown(id=2, title="parse", dependencies=[1]),
            TaskBreakdown(id=3, title="days", dependencies=[2]),
        ],
    )

    # Yesterday's run: everything failed, then was rejected.
    for item in plan.tasks:
        plan.record(
            TaskExecution(
                task_id=item.id,
                status=ExecutionStatus.FAILED,
                started_at=stamp(600),
                completed_at=stamp(599),
                error="Rejected in review",
            )
        )

    # Today's run: task 1 done, task 2 under way.
    plan.record(
        TaskExecution(task_id=1, status=ExecutionStatus.COMPLETED, started_at=stamp(2), completed_at=stamp(1))
    )

    PlanRepository().save(plan)

    run = PlanRun(plan_id=plan.id, repository_path=root, started_at=stamp(3))

    RunRepository().save(run)

    RunRepository().mark_started(run.id, os.getpid())

    RunRepository().progress(run.id, 2, ["record-1"])

    # The worker is this process, which is certainly alive.
    plan_runner.process_alive = lambda pid: True

    app = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")

    at = AppTest.from_file(app, default_timeout=60)

    at.session_state.repository_id = repository.id

    at.session_state.plan = PlanRepository().get_by_id(plan.id)

    at.run()

    check("the page did not fail", [e.value for e in at.exception], [])

    labels = [expander.label for expander in at.expander if " [" in expander.label]

    check(
        "done in this run, running now, and waiting -- not three failures",
        labels,
        ["✅ 1. types [MEDIUM] · COMPLETED", "⏳ 2. parse [MEDIUM] · RUNNING", "🕒 3. days [MEDIUM] · QUEUED"],
    )

    check(
        "the old failure is not shown for the task still to come",
        any("Rejected in review" in item.value for item in at.error),
        False,
    )

finally:
    shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL RUN VIEW CHECKS PASSED")
print("=" * 80)
