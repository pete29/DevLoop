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
    print("THE HISTORY: PER DAY AND PER PLAN")
    print("=" * 80)

    from datetime import date

    days = costs.daily(tasks_of_month, [plan], date(2026, 10, 15), days=30)

    check("thirty days, today last", (len(days), days[-1][0], days[0][0]), (30, "2026-10-15", "2026-09-16"))

    by_day = dict(days)

    check(
        "a quiet day is 0, not missing; a plan's own costs count on its day",
        (by_day["2026-10-02"], by_day["2026-10-01"], by_day["2026-10-15"], by_day["2026-09-30"]),
        (0.0, 1.0, 0.15, 5.0),
    )

    check(
        "a task after the window is left out",
        "2026-10-31" in by_day,
        False,
    )

    other = Plan(epic="Second plan\n\nmore", created_at="2026-10-16T00:00:00+00:00")

    rows = costs.per_plan(records + [Task(plan_id=other.id, cost=2.0)], [plan, other])

    check(
        "plans by what they cost, the costliest first, titled by their first line",
        [(title, round(spent, 2)) for title, _, spent in rows],
        [("Second plan", 2.0), ("-", 1.05)],
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
    print("THE MONTH'S LIMIT")
    print("=" * 80)

    month = costs.this_month()

    spending = [Task(cost=0.40, created_at=f"{month}-02T10:00:00+00:00")]

    Settings.MONTH_COST_LIMIT = 0.5

    check("under it, nothing is stopped", costs.month_over(spending, [], month), False)

    spending.append(Task(cost=0.10, created_at=f"{month}-03T10:00:00+00:00"))

    check("at it, everything is", costs.month_over(spending, [], month), True)

    check("last month's spending does not count", costs.month_over(spending, [], "1999-01"), False)

    Settings.MONTH_COST_LIMIT = 0

    check("0 means no limit", costs.month_over(spending, [], month), False)

    print()
    print("=" * 80)
    print("AN ESTIMATE FROM RECENT TASKS")
    print("=" * 80)

    history = [
        Task(cost=cost, created_at=f"2026-10-{day:02d}T10:00:00+00:00")
        for day, cost in enumerate([0.04, 0.05, 0.06, 0.06, 0.08, 0.73], start=1)
    ]

    guess = costs.estimate(8, history)

    check("the median, not the mean", round(guess.typical, 3), 0.06)

    check("for every task left", round(guess.total, 2), 0.48)

    check("with the middle half as a range", round(guess.total_low, 2) < 0.48 < round(guess.total_high, 2), True)

    check("one task that went wrong does not set the figure", guess.total_high < 8 * 0.73, True)

    check("no history, no estimate", costs.estimate(8, [Task(cost=0.05)]), None)

    check("nothing left, no estimate", costs.estimate(0, history), None)

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
