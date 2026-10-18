"""The release smoke test: one small plan, end to end, on the real model.

    python evals/smoke.py              runs it and prints one line
    python evals/smoke.py --record     also writes that line into
                                       CHANGELOG.md under Unreleased

The offline tests script the model's answers; only a live run
shows whether today's prompts still get the answers the
factory expects. So before a release is tagged, one requirement
of two tasks goes the whole way a plan goes in DevLoop: the
Planner splits it, and the worker's own loop (plan_runner.work)
runs the tasks on the plan's branch, with every gate, the
Architect, QA and the stop rules. It runs on a fresh copy of
evals/fixture with git, against a throwaway database, and
pushes nothing.

It costs money: about $0.16 on 2026-10-18. It never runs in CI.
"""

import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ROOT)

# Before any DevLoop module reads it: never the real database.
FOLDER = tempfile.mkdtemp(prefix="devloop-smoke-")

os.environ["DEVLOOP_DATABASE"] = os.path.join(FOLDER, "smoke.db")
os.environ["DEVLOOP_NOTIFY"] = "0"

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))

from agents.planner_agent import PlannerAgent  # noqa: E402
from config.version import VERSION  # noqa: E402
from database.plan_repository import PlanRepository  # noqa: E402
from database.run_repository import RunRepository  # noqa: E402
from database.task_repository import TaskRepository  # noqa: E402
from models.plan_run import PlanRun  # noqa: E402
from services import plan_runner, usage_ledger  # noqa: E402
from workflows.workflow_orchestrator import WorkflowOrchestrator  # noqa: E402

FIXTURE = os.path.join(ROOT, "evals", "fixture")

CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")

# Small on purpose: two files, one using the other.
REQUIREMENT = """Add a password strength score.

- src/strength-score.ts exports `strengthScore(password: string): number`:
  one point for each rule in src/password-validator.ts the password
  passes, so 0 to the number of rules.
- src/strength-label.ts exports `strengthLabel(password: string): string`,
  built on strengthScore: "weak" below half the rules, "strong" when all
  pass, "medium" otherwise.
"""

# Most tasks to run, whatever the Planner says: a smoke test
# that grew would stop being cheap.
MAX_TASKS = 3


def git(work: str, *arguments: str) -> None:

    subprocess.run(["git", "-C", work, *arguments], check=True, capture_output=True)


def repository() -> str:
    """A copy of the fixture, as a git repository on main."""

    work = os.path.join(FOLDER, "repo")

    shutil.copytree(FIXTURE, work, ignore=shutil.ignore_patterns("node_modules"))

    # The fixture's own installed packages, borrowed: no npm install.
    modules = os.path.join(FIXTURE, "node_modules")

    if os.path.isdir(modules):
        subprocess.run(["cmd", "/c", "mklink", "/J", os.path.join(work, "node_modules"), modules], check=True, capture_output=True)

    with open(os.path.join(work, ".gitignore"), "w", encoding="utf-8") as handle:
        handle.write("node_modules/\n")

    git(work, "init", "--quiet", "--initial-branch=main")
    git(work, "config", "user.name", "DevLoop smoke")
    git(work, "config", "user.email", "smoke@devloop.invalid")
    git(work, "add", "-A")
    git(work, "commit", "--quiet", "-m", "fixture")

    return work


def run() -> dict:

    work = repository()

    spent = usage_ledger.mark()

    plans, runs, tasks = PlanRepository(), RunRepository(), TaskRepository()

    plan = PlannerAgent().execute(REQUIREMENT, "smoke", work)

    plan.tasks = plan.tasks[:MAX_TASKS]

    plans.save(plan)

    planned = len(plan.tasks)

    started = PlanRun(plan_id=plan.id, repository_path=work)

    runs.save(started)

    plan_runner.work(started.id, runs, plans, tasks, WorkflowOrchestrator())

    finished = runs.get_by_id(started.id)

    made = [tasks.get_by_id(task_id) for task_id in finished.produced]

    made = [task for task in made if task is not None]

    good = [
        task
        for task in made
        if task.compile_result.status.value == "PASSED"
        and task.test_result.status.value == "PASSED"
        and task.recommendation.value == "APPROVE"
    ]

    return {
        "planned": planned,
        "ran": len(made),
        "good": len(good),
        "run": f"{finished.status.value}" + (f": {finished.message.rstrip('.')}" if finished.message else ""),
        "scores": [task.architecture_score for task in made],
        "cost": usage_ledger.dollars(usage_ledger.since(spent)),
    }


def line(result: dict) -> str:
    """The result as one CHANGELOG line."""

    verdict = "passed" if result["good"] == result["planned"] and result["ran"] == result["planned"] else "FAILED"

    return (
        f"- Smoke test (v{VERSION}+, `evals/smoke.py`): {verdict} — "
        f"{result['good']}/{result['planned']} planned tasks compiled, passed their tests "
        f"and were approved (scores {', '.join(str(score) for score in result['scores']) or '-'}); "
        f"run {result['run']}; ${result['cost']:.4f}."
    )


def record(text: str, path: str = CHANGELOG) -> None:
    """Writes the line into CHANGELOG.md's Unreleased section."""

    with open(path, encoding="utf-8", newline="") as handle:
        content = handle.read()

    newline = "\r\n" if "\r\n" in content else "\n"

    content = content.replace("\r\n", "\n")

    heading = "## Unreleased\n\n"

    if heading not in content:
        raise SystemExit("CHANGELOG.md has no '## Unreleased' section")

    section = "### Smoke test\n"

    start = content.index(heading) + len(heading)

    end = content.find("\n## ", start)

    unreleased = content[start:end if end != -1 else len(content)]

    if section in unreleased:
        at = start + unreleased.index(section) + len(section)
        content = content[:at] + text + "\n" + content[at:]

    else:
        content = content[:start] + section + text + "\n\n" + content[start:]

    with open(path, "w", encoding="utf-8", newline=newline) as handle:
        handle.write(content)


def clean_up() -> None:
    """Removes the copy; the borrowed node_modules link first, never its target."""

    link = os.path.join(FOLDER, "repo", "node_modules")

    if os.path.isjunction(link) or os.path.islink(link):
        os.rmdir(link) if os.path.isjunction(link) else os.unlink(link)

    shutil.rmtree(FOLDER, ignore_errors=True)


def main() -> int:

    try:
        result = run()

    finally:
        clean_up()

    text = line(result)

    print(text)

    if "--record" in sys.argv[1:]:
        record(text)
        print("written to CHANGELOG.md (Unreleased)")

    return 0 if "passed" in text.split("—")[0] else 1


if __name__ == "__main__":
    sys.exit(main())
