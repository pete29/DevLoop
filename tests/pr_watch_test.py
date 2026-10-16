"""Offline checks: an open pull request is asked about on its own.

Merging happens on GitHub, and DevLoop used to learn of it
only when someone pressed the refresh button. GitHub is
faked here; no network and no token:

    python -m tests.pr_watch_test
"""

import os
import tempfile

os.environ["DEVLOOP_DATABASE"] = os.path.join(tempfile.mkdtemp(), "watch.db")

from agents.pull_request_agent import PullRequestAgent  # noqa: E402
from models.plan import Plan  # noqa: E402
from models.pull_request_info import PullRequestInfo, PullRequestState  # noqa: E402
from models.task import Task  # noqa: E402
from ui import actions  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


ASKED: list[int] = []

ANSWER = {"state": PullRequestState.MERGED}


def fake_refresh(task):
    ASKED.append(task.pull_request.id)
    return PullRequestInfo(id=task.pull_request.id, url="u", branch="b", base="main", state=ANSWER["state"])


PullRequestAgent.refresh = staticmethod(fake_refresh)

STORED: list[tuple[str, object]] = []

actions.repository.update_pull_request = lambda record_id, info: STORED.append((record_id, info.state))

plan = Plan(repository_id="repo", epic="Epic")

holder = Task(repository_path="", description="one")

holder.pull_request = PullRequestInfo(id=12, url="u", branch="b", base="main", state=PullRequestState.OPEN)

other = Task(repository_path="", description="two")

state: dict = {}

print("=" * 80)
print("AN OPEN REQUEST IS ASKED ABOUT WHEN THE PLAN IS SHOWN")
print("=" * 80)

info = actions.check_open_request(plan, holder, [holder, other], state=state, clock=lambda: 100.0)

check("GitHub was asked (csv-kit #6: merged, shown as open)", ASKED, [12])

check("the merge is seen", info.state, PullRequestState.MERGED)

check("and stored on every record of the branch", [s for _, s in STORED], [PullRequestState.MERGED] * 2)

print()
print("=" * 80)
print("NOT ON EVERY RERUN")
print("=" * 80)

ASKED.clear()

actions.check_open_request(plan, holder, [holder], state=state, clock=lambda: 130.0)

check("half a minute later, it is not asked again", ASKED, [])

actions.check_open_request(plan, holder, [holder], state=state, clock=lambda: 161.0)

check("a minute later, it is", ASKED, [12])

print()
print("=" * 80)
print("A REQUEST THAT IS NO LONGER OPEN IS LEFT ALONE")
print("=" * 80)

ASKED.clear()

holder.pull_request = PullRequestInfo(id=12, url="u", branch="b", base="main", state=PullRequestState.MERGED)

actions.check_open_request(plan, holder, [holder], state={}, clock=lambda: 500.0)

check("a merged request is history", ASKED, [])

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL PR WATCH CHECKS PASSED")
print("=" * 80)
