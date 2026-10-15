"""Offline check: a task outside a plan runs like a planned one.

The real page, rendered headlessly against a throwaway
database; the worker is not started, so no model is called:

    python -m tests.standalone_task_test
"""

import os
import shutil
import tempfile

folder = tempfile.mkdtemp()

os.environ["DEVLOOP_DATABASE"] = os.path.join(folder, "standalone.db")

# A password in the developer's .env would stop the page at
# the sign-in screen; set, even empty, .env does not override it.
os.environ["DEVLOOP_PASSWORD_HASH"] = ""

from streamlit.testing.v1 import AppTest  # noqa: E402

from database.plan_repository import PlanRepository  # noqa: E402
from database.repository_repository import RepositoryRepository  # noqa: E402
from database.run_repository import RunRepository  # noqa: E402
from models.plan_run import RunStatus  # noqa: E402
from models.repository import Repository  # noqa: E402
from services import plan_runner  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


SPAWNED: list[str] = []

plan_runner.spawn_worker = lambda run: SPAWNED.append(run.id)

try:

    target = os.path.join(folder, "repo")

    os.makedirs(target)

    repository = Repository(name="repo", path=target)

    RepositoryRepository().save(repository)

    app = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")

    at = AppTest.from_file(app, default_timeout=60)

    at.run()

    at.session_state.repository_id = repository.id

    at.run()

    [area for area in at.text_area if area.label in ("Opisz zadanie dla AI", "Describe the task for the AI")][0].set_value(
        "Create a MaxLengthRule\n\nReject passwords longer than 128 characters."
    ).run()

    [button for button in at.button if button.label in ("Generuj kod", "Generate code")][0].click().run()

    check("the page did not fail", [e.value for e in at.exception], [])

    plans = PlanRepository().get_all()

    check("the task became a plan of one task", [len(plan.tasks) for plan in plans], [1])

    plan = plans[0]

    check(
        "its title and description are the task's",
        (plan.tasks[0].title, plan.tasks[0].description),
        ("Create a MaxLengthRule", "Reject passwords longer than 128 characters."),
    )

    run = RunRepository().latest(plan.id)

    check(
        "and it was handed to a background worker, not run in the page",
        (run is not None, run.task_id if run else None, run.status if run else None, SPAWNED == [run.id] if run else False),
        (True, 1, RunStatus.QUEUED, True),
    )

    check("the plan is the one on screen", at.session_state.plan.id, plan.id)

finally:
    shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL STANDALONE TASK CHECKS PASSED")
print("=" * 80)
