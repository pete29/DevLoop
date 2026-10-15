"""Offline checks for running a plan in the background.

The pipeline is faked, so the worker loop runs with no
model; one real worker process is started too, against a
throwaway database and a plan with nothing left to do:

    python -m tests.plan_runner_test
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time

folder = tempfile.mkdtemp()

database = os.path.join(folder, "runs.db")

# Before any database module is imported: their default
# database is bound at import time.
os.environ["DEVLOOP_DATABASE"] = database

# No real notification from the workers these checks start.
os.environ["DEVLOOP_NOTIFY"] = "0"

from database.plan_repository import PlanRepository  # noqa: E402
from database.run_repository import RunRepository  # noqa: E402
from database.task_repository import TaskRepository  # noqa: E402
from models.compile_result import CompileResult, CompileStatus  # noqa: E402
from models.plan import Plan  # noqa: E402
from models.plan_run import PlanRun, RunStatus  # noqa: E402
from models.task import Task  # noqa: E402
from models.task_breakdown import TaskBreakdown  # noqa: E402
from models.task_status import TaskStatus  # noqa: E402
from models.task_execution import ExecutionStatus, TaskExecution  # noqa: E402
from services import plan_runner  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


class Pipeline:
    """Stands in for the orchestrator; can fail or ask to stop."""

    def __init__(self, fail_on: str = "", stop_after: str = "", runs=None, broken: str = ""):
        self.fail_on = fail_on
        self.broken = broken
        self.stop_after = stop_after
        self.runs = runs
        self.ran: list[str] = []
        self.run_id = ""

    def execute(self, description, repository_id="", repository_path=""):
        title = description.splitlines()[0]
        self.ran.append(title)
        if title == self.fail_on:
            raise RuntimeError("the model refused")
        if title == self.stop_after:
            # The human presses Stop while this task runs.
            self.runs.request_stop(self.run_id)
        task = Task(
            repository_path=repository_path,
            description=description,
            status=TaskStatus.WAITING_FOR_APPROVAL,
        )
        if title == self.broken:
            task.compile_result = CompileResult(status=CompileStatus.FAILED)
        return task


def make_plan(plans: PlanRepository) -> Plan:

    plan = Plan(
        repository_id="repo",
        epic="Epic",
        tasks=[
            TaskBreakdown(id=1, title="one"),
            TaskBreakdown(id=2, title="two", dependencies=[1]),
            TaskBreakdown(id=3, title="three", dependencies=[2]),
        ],
    )

    plans.save(plan)

    return plan


def run_with(pipeline: Pipeline, plan: Plan, task_id: int = 0) -> PlanRun:

    run = PlanRun(plan_id=plan.id, task_id=task_id, repository_path=folder)

    runs.save(run)

    pipeline.run_id = run.id

    plan_runner.work(run.id, runs, plans, tasks, pipeline)

    return runs.get_by_id(run.id)


runs = RunRepository()
plans = PlanRepository()
tasks = TaskRepository()

try:

    print("=" * 80)
    print("THE PAGE'S STOP SURVIVES THE WORKER'S WRITES")
    print("=" * 80)

    run = PlanRun(plan_id="p")

    runs.save(run)

    runs.request_stop(run.id)

    runs.mark_started(run.id, 123)

    runs.progress(run.id, 2, ["t1"])

    stored = runs.get_by_id(run.id)

    check(
        "a stop asked before the worker started stays a stop",
        (stored.status, stored.pid, stored.current_task, stored.produced),
        (RunStatus.STOPPING, 123, 2, ["t1"]),
    )

    runs.finish(stored, RunStatus.STOPPED)

    runs.request_stop(run.id)

    check(
        "and a stop after the end does not reopen it",
        runs.get_by_id(run.id).status,
        RunStatus.STOPPED,
    )

    print()
    print("=" * 80)
    print("THE WORKER RUNS WHAT IS READY, IN ORDER")
    print("=" * 80)

    plan = make_plan(plans)

    pipeline = Pipeline()

    done = run_with(pipeline, plan)

    check("every task ran, in dependency order", pipeline.ran, ["one", "two", "three"])

    check("the run says so", (done.status, len(done.produced)), (RunStatus.DONE, 3))

    check(
        "the plan's executions are written, as the page wrote them",
        [
            item.status
            for item in sorted(plans.get_by_id(plan.id).executions, key=lambda e: e.task_id)
        ],
        [ExecutionStatus.COMPLETED] * 3,
    )

    check(
        "and each task record is saved",
        all(tasks.get_by_id(task_id) is not None for task_id in done.produced),
        True,
    )

    print()
    print("=" * 80)
    print("A STOP IS HONOURED BETWEEN TASKS, NEVER INSIDE ONE")
    print("=" * 80)

    plan = make_plan(plans)

    pipeline = Pipeline(stop_after="one", runs=runs)

    stopped = run_with(pipeline, plan)

    check("the task in hand finished", pipeline.ran, ["one"])

    check("then the run stopped", (stopped.status, len(stopped.produced)), (RunStatus.STOPPED, 1))

    print()
    print("=" * 80)
    print("A FAILURE STOPS THE RUN, AS RUN-ALL DID")
    print("=" * 80)

    plan = make_plan(plans)

    pipeline = Pipeline(fail_on="two")

    failed = run_with(pipeline, plan)

    check("nothing after the failure ran", pipeline.ran, ["one", "two"])

    check(
        "the run says which task and why",
        (failed.status, "Task 2" in failed.message, "refused" in failed.message),
        (RunStatus.FAILED, True, True),
    )

    check(
        "and the plan records the failure",
        plans.get_by_id(plan.id).execution(2).status,
        ExecutionStatus.FAILED,
    )

    print()
    print("=" * 80)
    print("CODE THAT DOES NOT COMPILE STOPS THE RUN")
    print("=" * 80)

    plan = make_plan(plans)

    pipeline = Pipeline(broken="one")

    halted = run_with(pipeline, plan)

    check("nothing was built on it", pipeline.ran, ["one"])

    check(
        "the run stopped, keeping the record for review",
        (halted.status, len(halted.produced), "Task 1" in halted.message),
        (RunStatus.STOPPED, 1, True),
    )

    print()
    print("=" * 80)
    print("ONE TASK, WHEN ONE WAS ASKED FOR")
    print("=" * 80)

    plan = make_plan(plans)

    pipeline = Pipeline()

    blocked = run_with(pipeline, plan, task_id=2)

    check(
        "a blocked task does not run",
        (pipeline.ran, blocked.status, "not ready" in blocked.message),
        ([], RunStatus.DONE, True),
    )

    single = run_with(pipeline, plan, task_id=1)

    check("a ready one runs once, and only it", (pipeline.ran, len(single.produced)), (["one"], 1))

    print()
    print("=" * 80)
    print("THE COST LIMIT STOPS A RUN BEFORE A TASK, NEVER IN ONE")
    print("=" * 80)

    from config.settings import Settings
    from services import usage_ledger

    class Priced(Pipeline):
        """Every task costs $2."""

        def execute(self, description, repository_id="", repository_path=""):
            task = super().execute(description, repository_id, repository_path)
            task.cost = 2.0
            return task

    Settings.PLAN_COST_LIMIT = 3.0

    plan = make_plan(plans)

    pipeline = Priced()

    limited = run_with(pipeline, plan)

    check(
        "it ran while under the limit, then stopped before the next task",
        (pipeline.ran, limited.status, "Cost limit reached: $4.00 of $3.00" in limited.message),
        (["one", "two"], RunStatus.STOPPED, True),
    )

    check(
        "and the records carry their plan",
        {tasks.get_by_id(task_id).plan_id for task_id in limited.produced},
        {plan.id},
    )

    Settings.PLAN_COST_LIMIT = 0

    from services import costs

    # Whatever this database has spent, plus one task's worth
    # minus a cent: the first task may start, the second not.
    Settings.MONTH_COST_LIMIT = costs.month_spent(tasks.get_all(), plans.get_all(), costs.this_month()) + 1.99

    plan = make_plan(plans)

    pipeline = Priced()

    monthly = run_with(pipeline, plan)

    check(
        "the month's limit stops a run before the next task",
        (pipeline.ran, monthly.status, "Monthly cost limit reached" in monthly.message),
        (["one"], RunStatus.STOPPED, True),
    )

    Settings.MONTH_COST_LIMIT = 0

    class Wasteful(Pipeline):
        """Spends, then fails before a record exists."""

        def execute(self, description, repository_id="", repository_path=""):
            usage_ledger.record(
                usage_ledger.Usage(role="developer", model="claude-sonnet-5-5", output_tokens=100_000)
            )
            raise RuntimeError("the model refused")

    plan = make_plan(plans)

    run_with(Wasteful(), plan)

    check(
        "what a failed attempt spent is kept on the plan",
        round(plans.get_by_id(plan.id).failed_cost, 2),
        1.0,
    )

    print()
    print("=" * 80)
    print("THE END OF A RUN IS ANNOUNCED")
    print("=" * 80)

    from services import notify as notify_module

    TOLD: list[tuple[str, str]] = []

    plan_runner.notify = lambda title, message: TOLD.append((title, message)) or True

    plan = make_plan(plans)

    run_with(Pipeline(), plan)

    check(
        "which plan, how it ended, and how many tasks wait",
        (TOLD[-1][0], TOLD[-1][1].startswith("Done. 3 task(s) wait for approval.")),
        ("DevLoop: Epic", True),
    )

    arguments, environment = notify_module.command('Plan "x"; Remove-Item C:\\', "msg")

    check(
        "the title reaches PowerShell as a variable, never as script text",
        ('Remove-Item' in " ".join(arguments), environment["DEVLOOP_TITLE"]),
        (False, 'Plan "x"; Remove-Item C:\\'),
    )

    check("and the switch turns it off", notify_module.notify("t", "m"), False)

    print()
    print("=" * 80)
    print("A WORKER THAT DIED IS FOUND BY ITS PROCESS")
    print("=" * 80)

    check("this process is alive", plan_runner.process_alive(os.getpid()), True)

    gone = subprocess.Popen([sys.executable, "-c", "pass"])

    gone.wait()

    check("a finished one is not", plan_runner.process_alive(gone.pid), False)

    check("nor is pid 0", plan_runner.process_alive(0), False)

    dead = PlanRun(plan_id="dead", status=RunStatus.RUNNING, pid=gone.pid, current_task=2)

    queued = PlanRun(plan_id="queued", status=RunStatus.QUEUED)

    runs.save(dead)

    runs.save(queued)

    found = plan_runner.detect_interrupted(runs)

    check("the dead run is interrupted", [run.id for run in found], [dead.id])

    check(
        "and says during which task",
        (runs.get_by_id(dead.id).status, "task 2" in runs.get_by_id(dead.id).message),
        (RunStatus.INTERRUPTED, True),
    )

    check(
        "a queued run, with no worker yet, is left alone",
        runs.get_by_id(queued.id).status,
        RunStatus.QUEUED,
    )

    runs.finish(runs.get_by_id(queued.id), RunStatus.STOPPED)

    print()
    print("=" * 80)
    print("ONE RUN PER PLAN, AND A REAL WORKER PROCESS")
    print("=" * 80)

    plan = make_plan(plans)

    for item in plan.tasks:
        plan.record(TaskExecution(task_id=item.id, status=ExecutionStatus.COMPLETED))

    plans.update_progress(plan)

    spawned: list[PlanRun] = []

    first = plan_runner.start(runs, plan.id, folder, spawn=spawned.append)

    refused = False

    try:
        plan_runner.start(runs, plan.id, folder, spawn=spawned.append)

    except RuntimeError:
        refused = True

    check("a second run of the same plan is refused", (refused, len(spawned)), (True, 1))

    # The queued run gets its real worker now. Every task is
    # done, so it ends without calling any model.
    plan_runner.spawn_worker(first)

    deadline = time.monotonic() + 60

    while time.monotonic() < deadline and runs.get_by_id(first.id).status.active:
        time.sleep(0.5)

    ended = runs.get_by_id(first.id)

    check(
        "the worker process ran and finished on its own",
        (ended.status, ended.message, ended.pid > 0 and ended.pid != os.getpid()),
        (RunStatus.DONE, "Every task has run.", True),
    )

    # Finished its work, maybe not yet exited: Windows keeps
    # the log locked until it has.
    while time.monotonic() < deadline and plan_runner.process_alive(ended.pid):
        time.sleep(0.2)

    with open(plan_runner.log_path(first), encoding="utf-8") as handle:
        console = handle.read()

    check("and wrote its console to the run's log", f"RUN {first.id}" in console, True)

    os.remove(plan_runner.log_path(first))

finally:
    for store in (runs, plans, tasks):
        store.connection.close()

    shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL PLAN RUNNER CHECKS PASSED")
print("=" * 80)
