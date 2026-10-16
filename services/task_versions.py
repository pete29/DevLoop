"""Which plan a task belongs to, and saving a newer version of it.

Used by the page and by the background worker alike: a
revision now runs in the worker, which cannot reach the
page's session.
"""

from models.requirement import now
from models.task_execution import ExecutionStatus, TaskExecution
from models.task_status import TaskStatus
from services import plan_branch


def plan_of(plans, tasks, task):
    """The plan a task belongs to, and every task on its branch.

    Found through the branch: the plan's branch name is
    derived from the plan, so a task records nothing more
    than the branch it ran on. (None, []) for a task that
    ran outside a plan.

    Plans made from the same issue share a branch, so the
    plan that ran this task wins, and otherwise the newest.
    """

    if not task.branch:
        return None, []

    on_branch = sorted(
        (item for item in plans.get_all() if plan_branch.of(item) == task.branch),
        key=lambda item: item.created_at,
        reverse=True,
    )

    plan = next(
        (
            item
            for item in on_branch
            if any(execution.task_record_id == task.id for execution in item.executions)
        ),
        on_branch[0] if on_branch else None,
    )

    if plan is None:
        return None, []

    return plan, [other for other in tasks.get_all() if other.branch == task.branch]


def replace_task(plans, tasks, task, newer):
    """Saves a newer version of a task in place of the old one.

    The old record becomes REVISED, and the plan's execution
    points at the new one, so the plan, the review state and
    the pull request all follow the latest version. Returns
    the newer record and the plan it updated, or None.
    """

    newer.branch = task.branch

    newer.issue = task.issue

    newer.plan_id = task.plan_id

    tasks.save(newer)

    task.status = TaskStatus.REVISED

    tasks.update_status(task.id, TaskStatus.REVISED)

    plan, _ = plan_of(plans, tasks, task)

    if plan is None:
        return newer, None

    for execution in plan.executions:

        if execution.task_record_id != task.id:
            continue

        plan.record(
            TaskExecution(
                task_id=execution.task_id,
                status=ExecutionStatus.COMPLETED,
                started_at=execution.started_at,
                completed_at=now(),
                task_record_id=newer.id,
            )
        )

        plans.update_progress(plan)

        break

    return newer, plan
