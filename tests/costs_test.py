"""Offline checks for what plans and months cost.

    python -m tests.costs_test
"""

import os
import shutil
import tempfile

folder = tempfile.mkdtemp()

os.environ["DEVLOOP_DATABASE"] = os.path.join(folder, "costs.db")

from config.settings import Settings  # noqa: E402
from database.plan_repository import PlanRepository  # noqa: E402
from database.task_repository import TaskRepository  # noqa: E402
from models.pipeline_step import PipelineStep  # noqa: E402
from models.plan import Plan  # noqa: E402
from models.task import Task  # noqa: E402
from models.task_execution import ExecutionStatus, TaskExecution  # noqa: E402
from services import costs, usage_ledger  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


try:

    print("=" * 80)
    print("A TASK'S COST")
    print("=" * 80)

    check("stored as a number", costs.task_cost(Task(cost=0.07)), 0.07)

    legacy = Task(
        steps=[
            PipelineStep(name="step.developer", detail="1 file(s)"),
            PipelineStep(
                name="step.usage",
                detail="developer 2× 1.8k->734 $0.01 · architect 1× 2.0k->876 $0.03 · total $0.04",
            ),
        ]
    )

    check("read from the usage line when saved before that", costs.task_cost(legacy), 0.04)

    check("nothing known is nothing spent", costs.task_cost(Task()), 0.0)

    check(
        "unpriced calls add up as zero, not as an error",
        usage_ledger.dollars(
            [
                usage_ledger.Usage(model="claude-opus-5-5", input_tokens=1_000_000),
                usage_ledger.Usage(model="unknown", input_tokens=1_000_000),
            ]
        ),
        4.0,
    )

    print()
    print("=" * 80)
    print("A PLAN'S COST: PLANNING, FAILURES, EVERY RECORD OF IT")
    print("=" * 80)

    plan = Plan(planning_cost=0.10, failed_cost=0.05, created_at="2026-10-15T08:00:00+00:00")

    old = Task(id="old", cost=0.20)

    plan.record(TaskExecution(task_id=1, status=ExecutionStatus.COMPLETED, task_record_id="old"))

    records = [
        old,
        # A revision replaced it; the replaced one still cost.
        Task(id="first-try", plan_id=plan.id, cost=0.30),
        Task(id="revision", plan_id=plan.id, cost=0.40),
        Task(id="elsewhere", plan_id="another-plan", cost=9.0),
        Task(id="loose", cost=9.0),
    ]

    check("every attempt of it counts, nothing else", round(costs.plan_spent(plan, records), 2), 1.05)

    print()
    print("=" * 80)
    print("A MONTH'S COST")
    print("=" * 80)

    tasks_of_month = [
        Task(cost=1.0, created_at="2026-10-01T00:00:00+00:00"),
        Task(cost=2.0, created_at="2026-10-31T23:00:00+00:00"),
        Task(cost=5.0, created_at="2026-09-30T23:00:00+00:00"),
    ]

    check(
        "this month's tasks and plans, not last month's",
        round(costs.month_spent(tasks_of_month, [plan], "2026-10"), 2),
        3.15,
    )

    print()
    print("=" * 80)
    print("THE LIMIT")
    print("=" * 80)

    Settings.PLAN_COST_LIMIT = 2.0

    check("under it, a task may start", costs.over_limit(1.99), False)

    check("at it, none may", costs.over_limit(2.0), True)

    Settings.PLAN_COST_LIMIT = 0

    check("0 means no limit", costs.over_limit(1000.0), False)

    print()
    print("=" * 80)
    print("COSTS SURVIVE STORAGE")
    print("=" * 80)

    tasks = TaskRepository()

    tasks.save(Task(id="stored", cost=0.12, plan_id="p-1"))

    loaded = tasks.get_by_id("stored")

    check("a task keeps its cost and its plan", (loaded.cost, loaded.plan_id), (0.12, "p-1"))

    plans = PlanRepository()

    plans.save(plan)

    plans.add_failed_cost(plan.id, 0.25)

    plans.add_failed_cost(plan.id, 0.25)

    again = plans.get_by_id(plan.id)

    check(
        "a plan keeps its planning cost, and failures add up in the database",
        (again.planning_cost, round(again.failed_cost, 2)),
        (0.10, 0.55),
    )

    tasks.connection.close()

    plans.connection.close()

finally:
    shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL COST CHECKS PASSED")
print("=" * 80)
