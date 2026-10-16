"""Offline check: planning runs in the background, and the page follows it.

The real page, headless, against a throwaway database; the
worker is not started, so no model is called -- the test
plays its part:

    python -m tests.jobs_view_test
"""

import os
import shutil
import tempfile

folder = tempfile.mkdtemp()

os.environ["DEVLOOP_DATABASE"] = os.path.join(folder, "jobs.db")

# A password in the developer's .env would stop the page at
# the sign-in screen; set, even empty, .env does not override it.
os.environ["DEVLOOP_PASSWORD_HASH"] = ""

from streamlit.testing.v1 import AppTest  # noqa: E402

from database.plan_repository import PlanRepository  # noqa: E402
from database.repository_repository import RepositoryRepository  # noqa: E402
from database.requirement_repository import RequirementRepository  # noqa: E402
from database.run_repository import RunRepository  # noqa: E402
from models.plan import Plan  # noqa: E402
from models.plan_run import RunStatus  # noqa: E402
from models.repository import Repository  # noqa: E402
from models.requirement import Requirement  # noqa: E402
from models.task_breakdown import TaskBreakdown  # noqa: E402
from services import plan_runner  # noqa: E402
from services.translations import translate  # noqa: E402

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

    root = os.path.join(folder, "repo")

    os.makedirs(root)

    repository = Repository(name="repo", path=root)

    RepositoryRepository().save(repository)

    requirement = Requirement(repository_id=repository.id, title="Dates", content="Add days to a date.")

    RequirementRepository().save(requirement)

    app = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")

    at = AppTest.from_file(app, default_timeout=60)

    at.session_state.repository_id = repository.id

    at.session_state.requirement = requirement

    at.run()

    [b for b in at.button if b.label == translate("requirement.generate_plan", "en")][0].click().run()

    check("the page did not fail", [e.value for e in at.exception], [])

    run = RunRepository().latest_job("planning", requirement.id)

    check(
        "planning is handed to a worker, not done in the page",
        (run is not None and run.kind, SPAWNED == [run.id] if run else False, run.status if run else None),
        ("planning", True, RunStatus.QUEUED),
    )

    check(
        "the page says the planner works in the background",
        any("background" in item.value for item in at.info),
        True,
    )

    check(
        "and does not offer to plan it twice",
        [b.disabled for b in at.button if b.label == translate("requirement.generate_plan", "en")],
        [True],
    )

    # The worker's part: a plan, and the run done.
    plan = Plan(repository_id=repository.id, epic="Dates", requirement_id=requirement.id, tasks=[TaskBreakdown(id=1, title="days")])

    PlanRepository().save(plan)

    store = RunRepository()

    store.progress(run.id, 0, [plan.id])

    store.finish(store.get_by_id(run.id), RunStatus.DONE, "Planned 1 task(s).")

    at.run()

    check("the page did not fail", [e.value for e in at.exception], [])

    check("when it ends, the plan it made is opened", at.session_state.plan.id if at.session_state.plan else None, plan.id)

finally:
    shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL JOBS VIEW CHECKS PASSED")
print("=" * 80)
