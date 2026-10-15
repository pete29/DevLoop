"""The factory, measured: the same work through the real pipeline.

    python evals/run_eval.py [label]

Each case in evals/cases.json runs on a fresh copy of
evals/fixture, a small TypeScript project with existing code
to build on. Three kinds:

- a task: one task through the whole pipeline -- Developer,
  free checks, Architect, QA, tests;
- a task that needs packages: the same, and when it stops
  for a missing npm package the eval does what the human's
  button does -- installs it on the copy and checks the same
  files again -- and records what it asked for;
- a plan: the Planner turns a requirement into tasks, and
  each task then runs in dependency order on the same copy.

The report says, per case, whether the result compiles and
passes its tests, what the Architect made of it, how many
rounds it took and what it cost; it is written to
evals/reports/<date>-<label>.json.

It calls the real model and costs money (about $0.30 for
the six cases), so it never runs in CI. Run it before and
after a change to a prompt or a setting, and compare:

    python evals/compare.py evals/reports/a.json evals/reports/b.json
"""

import json
import os
import shutil
import sys
import tempfile
import time
from datetime import UTC, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, ".env"))

from agents.planner_agent import PlannerAgent  # noqa: E402
from config.settings import Settings  # noqa: E402
from services import usage_ledger  # noqa: E402
from services.package_installer import add_packages, install  # noqa: E402
from workflows.workflow_orchestrator import WorkflowOrchestrator  # noqa: E402

FIXTURE = os.path.join(ROOT, "evals", "fixture")

CASES = os.path.join(ROOT, "evals", "cases.json")

REPORTS = os.path.join(ROOT, "evals", "reports")


def prepare_fixture() -> None:
    """Installs the fixture's dependencies once."""

    if os.path.isdir(os.path.join(FIXTURE, "node_modules")):
        return

    print("installing the fixture's dependencies (once) ...")

    result = install(FIXTURE)

    if not result.succeeded:
        sys.exit(f"could not install the fixture: {result.message}")


def outcome(task) -> dict:
    """What one finished task is worth measuring."""

    return {
        "compile": task.compile_result.status.value,
        "tests": task.test_result.status.value,
        "tests_passed": task.test_result.passed_tests,
        "tests_total": task.test_result.total_tests,
        "score": task.architecture_score,
        "recommendation": task.recommendation.value,
        "review_rounds": task.review_iterations,
        "blockers": len(task.blockers),
        "warnings": len(task.warnings),
        "files": sorted(item.path for item in task.generated_files),
    }


def passed(result: dict) -> bool:
    """What a good result is: it builds, its tests pass, it is approved."""

    return (
        result.get("compile") == "PASSED"
        and result.get("tests") == "PASSED"
        and result.get("recommendation") == "APPROVE"
    )


def run_task(case: dict, orchestrator: WorkflowOrchestrator, work: str) -> dict:

    task = orchestrator.execute(case["task"], "", work)

    result = {"packages_asked": list(task.packages)}

    if task.packages and case.get("install_packages"):

        installed = add_packages(work, task.packages)

        if not installed.succeeded:
            return {**result, "error": f"install failed: {installed.message}"}

        task = orchestrator.recheck(task)

    return {**result, **outcome(task)}


def run_plan(case: dict, orchestrator: WorkflowOrchestrator, work: str) -> dict:
    """The planner, then every task it planned, in order."""

    plan = PlannerAgent().execute(case["requirement"], "", work)

    done: list[dict] = []

    for item in plan.tasks:
        done.append({"task": item.title, **outcome(orchestrator.execute(item.prompt, "", work))})

    every = done

    return {
        "tasks": len(plan.tasks),
        "plan_problems": list(plan.issues),
        "compile": "PASSED" if every and all(e["compile"] == "PASSED" for e in every) else "FAILED",
        "tests": "PASSED" if every and all(e["tests"] == "PASSED" for e in every) else "FAILED",
        "tests_passed": every[-1]["tests_passed"] if every else 0,
        "tests_total": every[-1]["tests_total"] if every else 0,
        "score": min((e["score"] for e in every), default=0),
        "recommendation": "APPROVE" if every and all(e["recommendation"] == "APPROVE" for e in every) else "REQUEST_CHANGES",
        "review_rounds": sum(e["review_rounds"] for e in every),
        "per_task": done,
    }


KINDS = {"task": run_task, "plan": run_plan}


def run_case(case: dict, orchestrator: WorkflowOrchestrator) -> dict:

    folder = tempfile.mkdtemp(prefix=f"eval-{case['id']}-")

    work = os.path.join(folder, "repo")

    shutil.copytree(FIXTURE, work)

    spent = usage_ledger.mark()

    began = time.monotonic()

    try:
        result = KINDS[case.get("kind", "task")](case, orchestrator, work)

    except Exception as error:  # noqa: BLE001
        result = {"error": str(error)}

    finally:
        shutil.rmtree(folder, ignore_errors=True)

    calls = usage_ledger.since(spent)

    return {
        "id": case["id"],
        "kind": case.get("kind", "task"),
        **result,
        "cost": round(usage_ledger.dollars(calls), 4),
        "output_tokens": sum(call.output_tokens for call in calls),
        "seconds": round(time.monotonic() - began, 1),
    }


def main() -> None:

    label = sys.argv[1] if len(sys.argv) > 1 else "run"

    prepare_fixture()

    with open(CASES, encoding="utf-8") as handle:
        cases = json.load(handle)

    orchestrator = WorkflowOrchestrator()

    results = []

    for case in cases:

        print(f"\n=== {case['id']}: {case['what']}")

        result = run_case(case, orchestrator)

        result["passed"] = passed(result)

        results.append(result)

        print(f"--> {json.dumps(result)}")

    report = {
        "label": label,
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "models": dict(Settings.CLAUDE_MODELS),
        "efforts": dict(Settings.CLAUDE_EFFORTS),
        "results": results,
        "total_cost": round(sum(r.get("cost", 0) for r in results), 4),
        "passed": sum(1 for r in results if r["passed"]),
    }

    os.makedirs(REPORTS, exist_ok=True)

    name = f"{datetime.now(UTC):%Y-%m-%d}-{label}.json"

    with open(os.path.join(REPORTS, name), "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)

    print()
    print(table(report))
    print(f"\nwritten to evals/reports/{name}")


def table(report: dict) -> str:

    rows = [
        f"{'case':22} {'ok':3} {'compile':8} {'tests':9} {'score':5} {'rounds':6} {'cost':>8} {'out':>6} {'secs':>6}  notes",
    ]

    for r in report["results"]:

        if "error" in r:
            rows.append(f"{r['id']:22} {'no':3} ERROR: {r['error'][:60]}")
            continue

        notes = []

        if r.get("packages_asked"):
            notes.append("asked for " + ", ".join(r["packages_asked"]))

        if "tasks" in r:
            notes.append(f"{r['tasks']} tasks, {len(r.get('plan_problems', []))} plan problems")

        rows.append(
            f"{r['id']:22} {'yes' if r['passed'] else 'no':3} {r['compile']:8} "
            f"{r['tests_passed']}/{r['tests_total']:<7} {r['score']:5} {r['review_rounds']:6} "
            f"${r['cost']:7.4f} {r['output_tokens']:6} {r['seconds']:6}  {'; '.join(notes)}"
        )

    rows.append(
        f"\n{report['passed']}/{len(report['results'])} passed, ${report['total_cost']:.4f} in all"
    )

    return "\n".join(rows)


if __name__ == "__main__":
    main()
