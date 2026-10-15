"""What a plan, and a month, have cost.

Each task said what it cost and nothing added it up, so a
plan could spend without anyone seeing the total, and
nothing stopped a run that kept going.
"""

import re
import statistics
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from config.settings import Settings

# The end of a task's usage line: "... · total $0.04".
TOTAL = re.compile(r"total \$(\d+(?:\.\d+)?)")


def task_cost(task) -> float:
    """A task's dollars; read from its usage line if older.

    Tasks saved before costs were stored as a number still
    carry them in the step that reports usage.
    """

    if task.cost:
        return task.cost

    for step in task.steps:

        if step.name != "step.usage":
            continue

        found = TOTAL.search(step.detail)

        if found:
            return float(found.group(1))

    return 0.0


def plan_spent(plan, tasks) -> float:
    """Planning, failed attempts, and every task record of it.

    A record belongs to the plan when it says so, or -- for
    records saved before they did -- when an execution of
    the plan points at it. Revisions and reruns are records
    of their own, so they count too.
    """

    referenced = {
        execution.task_record_id
        for execution in plan.executions
        if execution.task_record_id
    }

    return (
        plan.planning_cost
        + plan.failed_cost
        + sum(
            task_cost(task)
            for task in tasks
            if task.plan_id == plan.id
            or (not task.plan_id and task.id in referenced)
        )
    )


def month_spent(tasks, plans, month: str) -> float:
    """Everything spent in a month, "YYYY-MM"."""

    return sum(
        task_cost(task)
        for task in tasks
        if task.created_at.startswith(month)
    ) + sum(
        plan.planning_cost + plan.failed_cost
        for plan in plans
        if plan.created_at.startswith(month)
    )


def daily(tasks, plans, today: date, days: int = 30) -> list[tuple[str, float]]:
    """Dollars per day for the last `days` days, today included.

    Every day is listed, a day with nothing spent as 0: a
    gap in a chart reads as missing data, not as a quiet day.
    A plan's planning and failed attempts count on the day
    the plan was made.
    """

    first = today - timedelta(days=days - 1)

    spent = {
        (first + timedelta(days=offset)).isoformat(): 0.0
        for offset in range(days)
    }

    for task in tasks:
        day = task.created_at[:10]
        if day in spent:
            spent[day] += task_cost(task)

    for plan in plans:
        day = plan.created_at[:10]
        if day in spent:
            spent[day] += plan.planning_cost + plan.failed_cost

    return [(day, round(value, 4)) for day, value in spent.items()]


def per_plan(tasks, plans) -> list[tuple[str, str, float]]:
    """(plan title, created day, dollars) per plan, costliest first."""

    rows = [
        (
            (plan.epic.strip().splitlines() or ["-"])[0][:80],
            plan.created_at[:10],
            round(plan_spent(plan, tasks), 4),
        )
        for plan in plans
    ]

    return sorted(rows, key=lambda row: row[2], reverse=True)


# How many recent tasks an estimate is drawn from.
RECENT_TASKS = 30


@dataclass
class Estimate:
    """What the remaining tasks of a plan will likely cost."""

    tasks: int

    # Per task: the middle half of recent tasks, and their median.
    low: float

    typical: float

    high: float

    # How many recent tasks the figures come from.
    sample: int

    @property
    def total(self) -> float:
        return self.tasks * self.typical

    @property
    def total_low(self) -> float:
        return self.tasks * self.low

    @property
    def total_high(self) -> float:
        return self.tasks * self.high


def estimate(remaining: int, tasks) -> Estimate | None:
    """What `remaining` tasks will likely cost, from recent ones.

    The median and quartiles, not the mean: one task that
    went wrong cost $0.73 where its neighbours cost $0.05,
    and a mean would have tripled every estimate after it.
    None without history, or with nothing left to run.
    """

    recent = sorted(
        (task for task in tasks if task_cost(task) > 0),
        key=lambda task: task.created_at,
        reverse=True,
    )[:RECENT_TASKS]

    if not remaining or len(recent) < 2:
        return None

    spent = sorted(task_cost(task) for task in recent)

    low, typical, high = statistics.quantiles(spent, n=4, method="inclusive")

    return Estimate(remaining, low, typical, high, len(spent))


def this_month() -> str:
    """"YYYY-MM" in UTC, the zone every record is stamped in."""

    return datetime.now(timezone.utc).strftime("%Y-%m")


def month_limit() -> float:

    return float(Settings.MONTH_COST_LIMIT or 0)


def month_over(tasks, plans, month: str | None = None) -> bool:
    """Whether this month's spending has reached its limit."""

    return month_limit() > 0 and month_spent(tasks, plans, month or this_month()) >= month_limit()


def limit() -> float:

    return float(Settings.PLAN_COST_LIMIT or 0)


def over_limit(spent: float) -> bool:
    """Whether a plan may not start another task.

    Checked before a task, never during one: half a task is
    files nobody reviews, and costs no less for being cut.
    """

    return limit() > 0 and spent >= limit()
