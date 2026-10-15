"""Runs a plan's tasks in a process of their own.

"Run the whole plan" used to run inside the Streamlit
request: the tab could not be closed, nothing could stop it
cleanly, and saving app.py -- which reruns the page --
interrupted the task being generated. Now the page starts
a worker and only reads what it writes:

    python -m services.plan_runner <run id>

Everything a run does is what the page did before: enter
the plan's branch, run the pipeline, save the task record,
write the plan's execution. Moved here so both can call it.
"""

import os
import subprocess
import sys

from database.plan_repository import PlanRepository
from database.run_repository import RunRepository
from database.task_repository import TaskRepository
from models.compile_result import CompileStatus
from models.pipeline_step import PipelineStep
from models.plan_run import PlanRun, RunStatus
from models.task_execution import ExecutionStatus, TaskExecution
from models.requirement import now
from services import costs, plan_branch, usage_ledger
from services.notify import notify
from services.git_service import GitService

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where each run's console goes: the pipeline prints what
# it is doing ("DEVELOPER: writing src/x.ts (3/8)"), and
# that is the only progress there is inside a task.
LOG_FOLDER = os.path.join(ROOT, "storage", "runs")


def log_path(run: PlanRun) -> str:

    return os.path.join(LOG_FOLDER, run.log_name)


def run_task(
    orchestrator,
    tasks: TaskRepository,
    description: str,
    repository_id: str,
    path: str,
    issue=None,
    branch: str = "",
    branch_note: str = "",
    plan_id: str = "",
):
    """One task through the whole pipeline, saved."""

    generated = orchestrator.execute(
        description,
        repository_id,
        path,
    )

    generated.branch = branch

    generated.plan_id = plan_id

    # First, because it happened first: the branch was
    # entered before anything was generated.
    if branch:
        generated.steps.insert(
            0,
            PipelineStep(
                name="step.branch",
                detail=branch
                + (f" · {branch_note}" if branch_note else ""),
            ),
        )

    if issue is not None and issue.exists:
        generated.issue = issue

    tasks.save(generated)

    return generated


def mark_running(plans: PlanRepository, plan, item) -> str:
    """Writes RUNNING before any work starts.

    Saved first, so the page shows the task as running
    *while* it runs -- and an interrupted run still reads
    as RUNNING when the app comes back.
    """

    started = now()

    plan.record(
        TaskExecution(
            task_id=item.id,
            status=ExecutionStatus.RUNNING,
            started_at=started,
        )
    )

    plans.update_progress(plan)

    return started


def execute_planned(
    orchestrator,
    tasks: TaskRepository,
    plans: PlanRepository,
    plan,
    item,
    target_path: str,
    started: str = "",
):
    """Runs one planned task, recording how it went.

    A failure is written down, so re-opening the plan shows
    what went wrong rather than offering the task again as
    if nothing had happened. Returns (task, "") or
    (None, the reason).
    """

    started = started or mark_running(plans, plan, item)

    spent = usage_ledger.mark()

    try:

        # The plan's branch is checked out before anything
        # is generated, so the task is written against the
        # code of the tasks before it -- and committed
        # where that code is.
        entered = plan_branch.Entered("")

        if GitService(target_path).is_repository():
            entered = plan_branch.enter(
                target_path,
                plan_branch.of(plan),
            )

        generated = run_task(
            orchestrator,
            tasks,
            item.prompt,
            plan.repository_id,
            target_path,
            plan.issue,
            entered.branch,
            entered.note,
            plan.id,
        )

    except Exception as error:

        # No record will carry what this attempt spent, so
        # the plan does: a failure is not free.
        wasted = usage_ledger.dollars(usage_ledger.since(spent))

        if wasted:
            plans.add_failed_cost(plan.id, wasted)

        plan.record(
            TaskExecution(
                task_id=item.id,
                status=ExecutionStatus.FAILED,
                started_at=started,
                completed_at=now(),
                error=str(error),
            )
        )

        plans.update_progress(plan)

        return None, str(error)

    plan.record(
        TaskExecution(
            task_id=item.id,
            status=ExecutionStatus.COMPLETED,
            started_at=started,
            completed_at=now(),
            task_record_id=generated.id,
        )
    )

    plans.update_progress(plan)

    return generated, ""


# ---------------------------------------------------------------- processes


def process_alive(pid: int) -> bool:
    """Whether a process still runs. Asked, never signalled.

    On Windows os.kill(pid, 0) does not test a process, it
    terminates it, so the question goes through the API
    that only reads.
    """

    if pid <= 0:
        return False

    if os.name != "nt":

        try:
            os.kill(pid, 0)

        except ProcessLookupError:
            return False

        except PermissionError:
            return True

        return True

    import ctypes

    kernel = ctypes.windll.kernel32

    handle = kernel.OpenProcess(0x1000, False, pid)

    if not handle:
        return False

    code = ctypes.c_ulong()

    try:
        kernel.GetExitCodeProcess(handle, ctypes.byref(code))

    finally:
        kernel.CloseHandle(handle)

    return code.value == 259


def detect_interrupted(runs: RunRepository) -> list[PlanRun]:
    """Marks active runs whose worker is gone as INTERRUPTED.

    A worker that was killed writes nothing, so the only
    evidence is its process. A run still QUEUED has had no
    worker yet and is left to start.
    """

    found = []

    for run in runs.active():

        if run.status == RunStatus.QUEUED:
            continue

        if process_alive(run.pid):
            continue

        runs.finish(
            run,
            RunStatus.INTERRUPTED,
            (
                f"The worker stopped during task {run.current_task}; "
                "files it wrote may be on disk, uncommitted."
                if run.current_task
                else "The worker stopped between tasks."
            ),
        )

        found.append(run)

    return found


def start(
    runs: RunRepository,
    plan_id: str,
    repository_path: str,
    task_id: int = 0,
    spawn=None,
) -> PlanRun:
    """Starts a background run, one per plan at a time.

    Detached from the page's process, so closing the tab,
    a rerun, or saving app.py does not reach it. `spawn` is
    for tests.
    """

    detect_interrupted(runs)

    if any(run.plan_id == plan_id for run in runs.active()):
        raise RuntimeError("This plan is already running.")

    run = PlanRun(
        plan_id=plan_id,
        task_id=task_id,
        repository_path=repository_path,
    )

    runs.save(run)

    os.makedirs(LOG_FOLDER, exist_ok=True)

    (spawn or spawn_worker)(run)

    return run


def spawn_worker(run: PlanRun) -> None:

    flags = 0

    if os.name == "nt":
        # A process group of its own, and no console window:
        # Ctrl+C in the terminal that runs Streamlit does
        # not reach it.
        flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.CREATE_NO_WINDOW
        )

    with open(log_path(run), "a", encoding="utf-8") as log:

        subprocess.Popen(
            [sys.executable, "-m", "services.plan_runner", run.id],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env={
                **os.environ,
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
                "PYTHONUNBUFFERED": "1",
            },
            creationflags=flags,
            close_fds=True,
        )


def work(
    run_id: str,
    runs: RunRepository,
    plans: PlanRepository,
    tasks: TaskRepository,
    orchestrator,
) -> PlanRun:
    """The worker: task after task until none is ready.

    Stops on the first failure, as run-all did, and checks
    for a stop request between tasks -- never inside one,
    because half a task is files on disk nobody reviews.
    """

    run = runs.get_by_id(run_id)

    runs.mark_started(run.id, os.getpid())

    print(f"RUN {run.id} for plan {run.plan_id} started", flush=True)

    while True:

        current = runs.get_by_id(run.id)

        if current.status == RunStatus.STOPPING:
            runs.finish(run, RunStatus.STOPPED, "Stopped by request.")
            break

        plan = plans.get_by_id(run.plan_id)

        if plan is None:
            runs.finish(run, RunStatus.FAILED, "The plan no longer exists.")
            break

        if run.task_id:
            item = plan.task(run.task_id)

            # One task: it runs once, and only if it may.
            if item is None or run.produced or not plan.is_ready(item):
                runs.finish(
                    run,
                    RunStatus.DONE,
                    "" if run.produced else "The task is not ready to run.",
                )
                break

        else:
            item = plan.next_ready()

        if item is not None:

            spent = costs.plan_spent(plan, tasks.get_all())

            if costs.month_over(tasks.get_all(), plans.get_all()):
                runs.finish(
                    run,
                    RunStatus.STOPPED,
                    f"Monthly cost limit reached: ${costs.month_limit():.2f}; "
                    f"task {item.id} not started.",
                )
                break

            if costs.over_limit(spent):
                runs.finish(
                    run,
                    RunStatus.STOPPED,
                    f"Cost limit reached: ${spent:.2f} of "
                    f"${costs.limit():.2f}; task {item.id} not started.",
                )
                break

        if item is None:
            runs.finish(
                run,
                RunStatus.DONE,
                (
                    "Every task has run."
                    if not plan.remaining
                    else f"Task {plan.remaining[0].id} waits for "
                    + ", ".join(str(d) for d in plan.blocked_by(plan.remaining[0]))
                    + "."
                ),
            )
            break

        runs.progress(run.id, item.id, run.produced)

        print(f"RUN task {item.id}: {item.title}", flush=True)

        generated, problem = execute_planned(
            orchestrator,
            tasks,
            plans,
            plan,
            item,
            run.repository_path,
        )

        if problem:
            runs.finish(run, RunStatus.FAILED, f"Task {item.id}: {problem}")
            break

        run.produced.append(generated.id)

        runs.progress(run.id, 0, run.produced)

        # The next task compiles the whole project, this
        # task's files included: one broken file fails every
        # task after it, each paying to try to fix it.
        if generated.compile_result.status == CompileStatus.FAILED:
            runs.finish(
                run,
                RunStatus.STOPPED,
                f"Task {item.id} does not compile; the tasks after "
                "it would build on it. Review it first.",
            )
            break

    print(f"RUN {run.id} ended: {run.status.value} {run.message}", flush=True)

    announce(run, plans, tasks)

    return run


def announce(run: PlanRun, plans: PlanRepository, tasks: TaskRepository) -> bool:
    """Tells the desktop the run ended: which plan, how, what waits."""

    plan = plans.get_by_id(run.plan_id)

    title = (plan.epic.strip().splitlines() or ["DevLoop"])[0] if plan else "DevLoop"

    waiting = sum(
        1
        for task_id in run.produced
        if (task := tasks.get_by_id(task_id)) is not None
        and task.status.value == "WAITING_FOR_APPROVAL"
    )

    ending = {
        RunStatus.DONE: "Done",
        RunStatus.STOPPED: "Stopped",
        RunStatus.FAILED: "Failed",
    }.get(run.status, run.status.value)

    message = f"{ending}. {waiting} task(s) wait for approval." + (
        f" {run.message}" if run.message else ""
    )

    return notify(f"DevLoop: {title}", message)


if __name__ == "__main__":

    from dotenv import load_dotenv

    load_dotenv(os.path.join(ROOT, ".env"))

    from workflows.workflow_orchestrator import WorkflowOrchestrator

    store = RunRepository()

    try:
        work(
            sys.argv[1],
            store,
            PlanRepository(),
            TaskRepository(),
            WorkflowOrchestrator(),
        )

    except Exception as error:

        failed = store.get_by_id(sys.argv[1])

        if failed is not None and failed.status.active:
            store.finish(failed, RunStatus.FAILED, f"The worker crashed: {error}")

        raise
