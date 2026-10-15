"""What the page does, apart from drawing: runs, revisions, plans continued."""

import streamlit as st

from agents.planner_agent import PlannerAgent
from models.repository import Repository
from models.requirement import now
from models.task_execution import ExecutionStatus, TaskExecution
from models.task_status import TaskStatus
from services import plan_branch, plan_runner, usage_ledger
from services.git_service import GitError, GitService
from services.task_rollback import Rollback, roll_back_all
from ui import shared
from ui.shared import orchestrator, plan_store, repository, repository_path_now, repository_store, run_store, t


def plan_records(plan) -> list:
    """Every task record that ran on this plan's branch."""

    branch = plan_branch.of(plan)

    return sorted(
        (
            other
            for other in repository.get_all()
            if other.branch == branch
        ),
        key=lambda other: other.created_at,
    )


def waiting_records(plan) -> list:
    """The plan's records still waiting for a decision."""

    return [
        record
        for record in plan_records(plan)
        if record.status == TaskStatus.WAITING_FOR_APPROVAL
        and not record.git_operation.committed
    ]


def reject_plan(plan) -> tuple[int, Rollback]:
    """Rejects every waiting record of the plan, files first.

    One click for what a broken run leaves behind: eight
    tasks rejected one window at a time, and the files
    they wrote removed by hand.
    """

    records = waiting_records(plan)

    undone = roll_back_all(records)

    for record in records:

        reopen_in_plan(record)

        repository.update_status(record.id, TaskStatus.REJECTED)

    return len(records), undone


def plan_pull_request(records):
    """The plan's pull request as last read, or None.

    Stored on the task that opened or last refreshed it;
    every task on the branch shares the one request.
    """

    known = [
        record
        for record in records
        if record.pull_request.exists
    ]

    return known[-1] if known else None


def register_repository(name: str, path: str) -> None:
    """Saves a repository and makes it the selected one."""

    added = Repository(name=name, path=path)

    repository_store.save(added)

    shared.select_repository(added.id)


def start_run(plan, target_path: str, task_id: int = 0) -> None:
    """Hands a plan, or one of its tasks, to a worker."""

    try:
        run = plan_runner.start(run_store, plan.id, target_path, task_id)

    except Exception as error:
        st.session_state.git_message = (
            "warning",
            t("run.could_not_start", reason=error),
        )

    else:
        st.session_state.watching_run = run.id

    st.rerun()


def log_tail(run, lines: int = 12) -> str:
    """The end of the worker's console, or ""."""

    try:
        with open(
            plan_runner.log_path(run),
            encoding="utf-8",
            errors="replace",
        ) as handle:
            return "\n".join(handle.read().splitlines()[-lines:])

    except OSError:
        return ""


def remote_of(repository_id: str) -> str:
    """The repository's remote URL, or "" without one."""

    known = shared.repositories_by_id.get(repository_id)

    if known is None or not GitService(known.path).is_repository():
        return ""

    try:
        return GitService(known.path).remote_url()

    except GitError:
        return ""


def continue_plan(plan) -> None:
    """Plans what a plan still needs, on its own branch.

    The branch is entered first, so the planner reads the
    code the plan has already committed rather than
    whatever another branch holds.
    """

    path = repository_path_now()

    spent = usage_ledger.mark()

    try:

        if path and GitService(path).is_repository():
            plan_branch.enter(path, plan_branch.of(plan))

        with st.spinner(t("plan.continue_spinner")):
            tasks, issues = PlannerAgent().extend(plan, path)

    except Exception as error:

        st.session_state.git_message = (
            "warning",
            t("plan.continue_failed", reason=error),
        )

        st.rerun()

    kept = sum(1 for item in tasks if plan.is_done(item.id))

    plan.tasks = tasks

    plan.issues = issues

    plan.planning_cost += usage_ledger.dollars(usage_ledger.since(spent))

    plan_store.replace_tasks(plan)

    st.session_state.plan = plan

    st.session_state.git_message = (
        "success",
        t("plan.continued", added=len(tasks) - kept, kept=kept),
    )

    st.rerun()


def install_and_recheck(task):
    """Installs a task's packages, then checks its files again.

    The install is the human's click; the recheck is a new
    record replacing the old one, as a revision is.
    """

    from services.package_installer import add_packages

    require_branch(task)

    result = add_packages(task.repository_path, task.packages)

    if not result.succeeded:
        raise RuntimeError(result.message + ("\n" + result.output[-800:] if result.output else ""))

    checked = orchestrator.recheck(task)

    return replace_task(task, checked)


def require_branch(task) -> None:
    """Refuses to work on a task's files from another branch.

    Its files are read from disk, and on another branch
    they are another branch's files.
    """

    if task.branch and GitService(task.repository_path).is_repository():

        current = GitService(task.repository_path).current_branch()

        if current != task.branch:
            raise ValueError(
                t(
                    "revise.wrong_branch",
                    branch=task.branch,
                    current=current,
                )
            )


def replace_task(task, newer):
    """Saves a newer version of a task in place of the old one."""

    newer.branch = task.branch

    newer.issue = task.issue

    newer.plan_id = task.plan_id

    repository.save(newer)

    task.status = TaskStatus.REVISED

    repository.update_status(task.id, TaskStatus.REVISED)

    plan, _ = plan_context(task)

    if plan is not None:

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

            plan_store.update_progress(plan)

            if (
                st.session_state.get("plan") is not None
                and st.session_state.plan.id == plan.id
            ):
                st.session_state.plan = plan

            break

    return newer


def plan_context(task):
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
        (
            item
            for item in plan_store.get_all()
            if plan_branch.of(item) == task.branch
        ),
        key=lambda item: item.created_at,
        reverse=True,
    )

    plan = next(
        (
            item
            for item in on_branch
            if any(
                execution.task_record_id == task.id
                for execution in item.executions
            )
        ),
        on_branch[0] if on_branch else None,
    )

    if plan is None:
        return None, []

    return plan, [
        other
        for other in repository.get_all()
        if other.branch == task.branch
    ]


def revise_task(task, feedback: str):
    """Sends a task back with a human's notes, saved.

    The revision is a new record on the same files; the
    old one becomes REVISED, and the plan's execution
    points at the new one, so the plan, the review state
    and the pull request all follow the latest version.
    """

    require_branch(task)

    return replace_task(task, orchestrator.revise(task, feedback))


def reopen_in_plan(task) -> None:
    """A rejected task counts as failed in its plan.

    Its execution said COMPLETED, so the plan showed it
    done, offered no way to run it again, and released the
    tasks that depend on it -- built on code nobody had
    accepted. FAILED is what it is: the run produced
    nothing usable. The plan then offers "run again", and
    the dependents wait.
    """

    plan, _ = plan_context(task)

    if plan is None:
        return

    for execution in plan.executions:

        if execution.task_record_id != task.id:
            continue

        plan.record(
            TaskExecution(
                task_id=execution.task_id,
                status=ExecutionStatus.FAILED,
                started_at=execution.started_at,
                completed_at=now(),
                error=t("plan.rejected_in_review"),
                task_record_id=task.id,
            )
        )

        plan_store.update_progress(plan)

        if (
            st.session_state.get("plan") is not None
            and st.session_state.plan.id == plan.id
        ):
            st.session_state.plan = plan

        return
