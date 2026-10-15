"""What a plan, and a month, have cost.

Each task said what it cost and nothing added it up, so a
plan could spend without anyone seeing the total, and
nothing stopped a run that kept going.
"""

import re

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


def limit() -> float:

    return float(Settings.PLAN_COST_LIMIT or 0)


def over_limit(spent: float) -> bool:
    """Whether a plan may not start another task.

    Checked before a task, never during one: half a task is
    files nobody reviews, and costs no less for being cut.
    """

    return limit() > 0 and spent >= limit()
