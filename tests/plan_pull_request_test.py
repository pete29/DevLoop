"""Offline checks for a plan's pull request.

GitHub is faked at the HTTP layer, so this runs with no
network and no token:

    python -m tests.plan_pull_request_test

A plan pushes its branch once per task. The pull request
used to describe whichever task opened it, and nothing
could change that afterwards; nor did anything notice when
a human merged it.
"""

import os

os.environ.setdefault("GITHUB_PAT", "ghp_faketoken")

import services.github_service as github
from models.file_type import FileType
from models.generated_file import GeneratedFile
from models.git_operation import GitOperation
from models.git_push_operation import (
    GitPushOperation,
    PushStatus,
)
from models.plan import Plan
from models.pull_request_info import PullRequestState
from models.requirement import Requirement, RequirementLifecycle
from models.task import Task
from models.task_breakdown import TaskBreakdown
from models.task_execution import ExecutionStatus, TaskExecution
from models.task_status import TaskStatus
from services.github_service import GitHubError, GitHubService
from workflows.review_decision import ReviewDecision

failures: list[str] = []


def check(
    label: str,
    actual: object,
    expected: object,
) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


CALLS: list[tuple[str, str, dict]] = []

# What GitHub answers to a search for the branch's request.
EXISTING: list[dict] = []


class FakeResponse:
    def __init__(self, status: int, payload=None) -> None:
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.headers = {}
        self.content = b"x"
        self.text = str(self._payload)

    def json(self):
        return self._payload


def fake_request(method: str, url: str, **kwargs):

    path = url.replace(github.API_ROOT, "")

    CALLS.append((method, path, kwargs.get("json") or {}))

    if method == "GET" and path.endswith("/pulls"):
        return FakeResponse(200, list(EXISTING))

    if method == "GET":
        return FakeResponse(200, {"default_branch": "main"})

    return FakeResponse(
        201 if method == "POST" else 200,
        {
            "number": 7,
            "html_url": "https://github.com/o/r/pull/7",
            "state": "open",
            "created_at": "2026-10-14T10:00:00Z",
            "base": {"ref": "main"},
        },
    )


github.requests.request = fake_request

from agents.pull_request_agent import (  # noqa: E402
    PullRequestAgent,
    plan_description,
    plan_title,
)
from agents.git_agent import summary  # noqa: E402

BRANCH = "feature/plan-abcdef12-walidator-hasel"


def record(
    description: str,
    path: str,
    committed: bool,
    status: TaskStatus = TaskStatus.APPROVED,
) -> Task:

    return Task(
        repository_path="C:/repo",
        description=description,
        architecture_score=88,
        recommendation=ReviewDecision.APPROVE,
        generated_files=[GeneratedFile(path, FileType.SOURCE)],
        warnings=[f"warning about {path}"],
        branch=BRANCH,
        git_operation=GitOperation(
            branch_name=BRANCH,
            commit_hash=("c" * 40) if committed else "",
        ),
        git_push=GitPushOperation(
            branch_name=BRANCH,
            remote_name="origin",
            remote_url="https://github.com/o/r.git",
            status=PushStatus.SUCCESS,
        ),
        status=status,
    )


plan = Plan(
    id="abcdef12-0000",
    epic="Walidator haseł\n\nSprawdza siłę hasła.",
    tasks=[
        TaskBreakdown(id=1, title="Rule contract"),
        TaskBreakdown(id=2, title="Rules", dependencies=[1]),
        TaskBreakdown(id=3, title="Validator", dependencies=[2]),
    ],
)

first = record("Create the rule contract.", "src/rule.ts", True)

second = record(
    "Create the rules.",
    "src/rules.ts",
    False,
    TaskStatus.WAITING_FOR_APPROVAL,
)

for task_id, done in ((1, first), (2, second)):
    plan.record(
        TaskExecution(
            task_id=task_id,
            status=ExecutionStatus.COMPLETED,
            task_record_id=done.id,
        )
    )

records = [first, second]

print("=" * 80)
print("THE DESCRIPTION COVERS THE WHOLE PLAN")
print("=" * 80)

body = plan_description(plan, records)

check(
    "the title is the requirement's",
    plan_title(plan),
    "feat: walidator haseł",
)

check(
    "the requirement is quoted",
    "Sprawdza siłę hasła." in body,
    True,
)

check(
    "a committed task is ticked",
    "- [x] **1. Rule contract** — committed ccccccc" in body,
    True,
)

check(
    "a task awaiting review is not",
    "- [ ] **2. Rules** — awaiting review" in body,
    True,
)

check(
    "a task never run says so",
    "- [ ] **3. Validator** — not run yet" in body,
    True,
)

check(
    "files are the committed ones only",
    ("src/rule.ts" in body, "src/rules.ts" in body),
    (True, False),
)

check(
    "findings come from committed work, named by task",
    "warning about src/rule.ts" in body
    and "warning about src/rules.ts" not in body,
    True,
)

check(
    "a finding is labelled like the checklist",
    "- **1. Rule contract**: warning about src/rule.ts" in body,
    True,
)

earlier = record("Old contract\n\nFrom the plan before.", "src/old.ts", True)

earlier.created_at = "2000-01-01T00:00:00+00:00"

shared = plan_description(plan, [earlier, *records])

check(
    "an earlier plan's commit on the shared branch is listed",
    "- [x] Old contract — earlier plan, committed ccccccc" in shared
    and "src/old.ts" in shared,
    True,
)

check(
    "and a task of this plan is not mistaken for one",
    "earlier plan" in body,
    False,
)

check(
    "a commit subject reads only the title line",
    summary("Utwórz regułę cyfry\n\nZaimplementuj klasę DigitRule."),
    "utwórz regułę cyfry",
)

print()
print("=" * 80)
print("MERGING THE WHOLE PLAN CLOSES ITS ISSUE, HALF OF IT DOES NOT")
print("=" * 80)

from models.github_issue import IssueLink  # noqa: E402

plan.issue = IssueLink(id=5870283902, number=2, title="Calendar date arithmetic", state="open", url="https://github.com/o/r/issues/2")

check("with tasks still to commit, it is only part of it", "Part of #2" in plan_description(plan, records), True)

check("and does not close it", "Closes #2" in plan_description(plan, records), False)

whole = Plan(id="abcdef12-0001", epic="Dates", tasks=[TaskBreakdown(id=1, title="Rule contract")], issue=plan.issue)

whole.record(TaskExecution(task_id=1, status=ExecutionStatus.COMPLETED, task_record_id=first.id))

check("every task committed: merging closes it", "Closes #2" in plan_description(whole, [first]), True)

check(
    "a plan without an issue names none",
    any(word in plan_description(Plan(id="x", epic="E", tasks=[]), []) for word in ("Closes #", "Part of #")),
    False,
)

plan.issue = IssueLink()

print()
print("=" * 80)
print("A PUSH REWRITES THE OPEN REQUEST")
print("=" * 80)

CALLS.clear()

EXISTING[:] = [
    {
        "number": 7,
        "state": "open",
        "html_url": "https://github.com/o/r/pull/7",
        "base": {"ref": "main"},
    }
]

info = PullRequestAgent.sync(first, plan, records)

patches = [call for call in CALLS if call[0] == "PATCH"]

check("one PATCH was sent", len(patches), 1)

check(
    "to the request that exists",
    patches[0][1] if patches else "",
    "/repos/o/r/pulls/7",
)

check(
    "with the title and body, nothing else",
    sorted(patches[0][2]) if patches else [],
    ["body", "title"],
)

check("and the request is reported", info.id, 7)

EXISTING[:] = [{"number": 7, "state": "closed"}]

CALLS.clear()

check(
    "a closed request is left alone",
    (
        PullRequestAgent.sync(first, plan, records),
        [c for c in CALLS if c[0] == "PATCH"],
    ),
    (None, []),
)

EXISTING[:] = []

check(
    "with no request, nothing is opened",
    PullRequestAgent.sync(first, plan, records),
    None,
)

print()
print("=" * 80)
print("OPENING THROUGH ANOTHER TASK UPDATES, NOT DUPLICATES")
print("=" * 80)

EXISTING[:] = [
    {
        "number": 7,
        "state": "open",
        "html_url": "https://github.com/o/r/pull/7",
        "base": {"ref": "main"},
    }
]

CALLS.clear()

# The first task is the approved, pushed one; the request
# was opened from elsewhere.
info = PullRequestAgent.execute(first, plan=plan, records=records)

check(
    "no second request is created",
    [c for c in CALLS if c[0] == "POST"],
    [],
)

check(
    "the existing one gets the plan's description",
    [c[2].get("title") for c in CALLS if c[0] == "PATCH"],
    ["feat: walidator haseł"],
)

print()
print("=" * 80)
print("A REQUEST MAY ONLY HAVE ITS TITLE AND BODY CHANGED")
print("=" * 80)

service = GitHubService("o", "r", token="tok")

for label, payload in (
    ("closing it", {"state": "closed"}),
    ("retargeting it", {"base": "release"}),
    ("a title smuggled with a state", {"title": "x", "state": "closed"}),
    ("an empty change", {}),
):

    try:
        service._request("PATCH", "/repos/o/r/pulls/7", payload)

        failures.append(label)

        print(f"FAIL {label}: it was allowed")

    except GitHubError:
        print(f"OK   refused: {label}")

print()
print("=" * 80)
print("A MERGED REQUEST MEANS DELIVERED")
print("=" * 80)

requirement = Requirement(title="Walidator haseł")

check(
    "every task ran, nothing merged: completed",
    requirement.lifecycle(plans=1, started=1, outstanding=0),
    RequirementLifecycle.COMPLETED,
)

check(
    "merged: delivered",
    requirement.lifecycle(
        plans=1, started=1, outstanding=0, delivered=1
    ),
    RequirementLifecycle.DELIVERED,
)

check(
    "work still outstanding wins over a merge",
    requirement.lifecycle(
        plans=1, started=1, outstanding=2, delivered=1
    ),
    RequirementLifecycle.EXECUTING,
)

check(
    "a merged state is read from GitHub's merged_at",
    PullRequestAgent.to_info(
        {"number": 7, "state": "closed", "merged_at": "2026-10-14"},
        BRANCH,
        "main",
    ).state,
    PullRequestState.MERGED,
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL PLAN PULL REQUEST CHECKS PASSED")
print("=" * 80)
