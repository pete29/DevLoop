"""The safe pull request workflow, as checks rather than prose.

Every rule in docs/SECURITY.md about what the agents may
and may not do is asserted here against the real allow
lists and the real services. A governance document nobody
runs is a document that drifts.

    python -m tests.governance_test
"""

import os
import subprocess
import tempfile

os.environ.setdefault("GITHUB_PAT", "ghp_faketoken")

import services.github_service as github
from services.git_service import (
    ALLOWED_COMMANDS,
    FORBIDDEN_COMMANDS,
    FORBIDDEN_PUSH_FLAGS,
    PROTECTED_BRANCHES,
    GitError,
    GitService,
)
from services.github_service import ALLOWED_CALLS, GitHubError

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


def refuses(label: str, call) -> None:

    try:
        call()

    except (GitError, GitHubError):
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: it was allowed")


def allowed(method: str, path: str) -> bool:

    return any(
        method == candidate and pattern.match(path)
        for candidate, pattern in ALLOWED_CALLS
    )


print("=" * 80)
print("GIT: WHAT THE AGENT MAY RUN")
print("=" * 80)

# The workflow document's list. The code allows a few more,
# each either read-only or, in fetch's case, writing only
# the remote-tracking refs -- and that is the only
# difference there is allowed to be.
for command in (
    "add",
    "branch",
    "checkout",
    "commit",
    "push",
    "rev-parse",
    "status",
    "symbolic-ref",
):
    check(
        f"'{command}' is allowed",
        command in ALLOWED_COMMANDS,
        True,
    )

check(
    "and nothing else beyond the read-only extras and fetch",
    sorted(
        ALLOWED_COMMANDS
        - {
            "add",
            "branch",
            "checkout",
            "commit",
            "push",
            "rev-parse",
            "status",
            "symbolic-ref",
        }
    ),
    # init: only `init --quiet --initial-branch=<name>`, for
    # "New repository"; remote adds only origin, once. Both
    # shapes are pinned in tests.repository_setup_test.
    # config: only reading or locally setting user.name and
    # user.email, pinned in tests.environment_test.
    ["config", "diff", "fetch", "init", "ls-files", "merge-base", "remote"],
)

# Fetch is allowed because a factory whose main never
# learns about merged pull requests plans on stale code.
# Pull is not: it would merge into a local branch.
for command in (
    "pull",
    "clone",
    "merge",
    "reset",
    "rebase",
    "cherry-pick",
):
    check(
        f"'{command}' is forbidden",
        command in FORBIDDEN_COMMANDS,
        True,
    )

    check(
        "and not quietly allowed as well",
        command in ALLOWED_COMMANDS,
        False,
    )

print()
print("=" * 80)
print("GIT: NO FORCE, NO DELETE, NO SHARED BRANCHES")
print("=" * 80)

for flag in (
    "--force",
    "-f",
    "--force-with-lease",
    "--mirror",
    "--delete",
    "--prune",
):
    check(
        f"'{flag}' is refused on a push",
        flag in FORBIDDEN_PUSH_FLAGS,
        True,
    )

for branch in ("main", "master", "develop"):
    check(
        f"'{branch}' is protected",
        branch in PROTECTED_BRANCHES,
        True,
    )

sandbox = tempfile.mkdtemp()

for args in (
    ["init", "-b", "work"],
    ["config", "user.email", "t@e.com"],
    ["config", "user.name", "T"],
    ["remote", "add", "origin", "https://example.invalid/o/r.git"],
):
    subprocess.run(
        ["git", "-C", sandbox, *args],
        capture_output=True,
        check=False,
    )

service = GitService(sandbox)

for branch in ("main", "master", "develop", "MAIN"):
    refuses(
        f"pushing {branch!r}",
        lambda name=branch: service.push_branch(name),
    )

refuses(
    "a branch name that would reach git as a flag",
    lambda: service.push_branch("--force"),
)

refuses(
    "a remote name that would reach git as a flag",
    lambda: service.push_branch("feature/x", "--upload-pack=sh"),
)

for command in ("merge", "reset", "pull", "rebase"):
    refuses(
        f"running '{command}' at all",
        lambda name=command: service._run(name),
    )

print()
print("=" * 80)
print("GIT: ONLY WHAT THE RUN PRODUCED IS STAGED")
print("=" * 80)

mine = os.path.join(sandbox, "mine.txt")

with open(mine, "w", encoding="utf-8") as handle:
    handle.write("a file the user wrote\n")

generated = os.path.join(sandbox, "generated.ts")

with open(generated, "w", encoding="utf-8") as handle:
    handle.write("export class Generated {}\n")

service.add(["generated.ts"])

check(
    "the generated file is staged",
    service.staged_files(),
    ["generated.ts"],
)

check(
    "and the user's file is not",
    "mine.txt" in service.staged_files(),
    False,
)

print()
print("=" * 80)
print("GITHUB: PREPARE A PULL REQUEST, NEVER DECIDE ONE")
print("=" * 80)

check(
    "a pull request can be opened",
    allowed("POST", "/repos/o/r/pulls"),
    True,
)

check(
    "and read",
    allowed("GET", "/repos/o/r/pulls/17"),
    True,
)

for method, path, what in (
    ("PUT", "/repos/o/r/pulls/17/merge", "merging"),
    ("POST", "/repos/o/r/merges", "merging by branch"),
    ("DELETE", "/repos/o/r/pulls/17", "deleting a pull request"),
    ("DELETE", "/repos/o/r/git/refs/heads/x", "deleting a branch"),
    ("POST", "/repos/o/r/pulls/17/reviews", "approving"),
    ("PUT", "/repos/o/r/contents/x.ts", "writing a file"),
    ("POST", "/repos/o/r/deployments", "deploying"),
    ("DELETE", "/repos/o/r", "deleting the repository"),
    ("GET", "/user", "reading the account"),
):
    check(f"{what} is not in the allow list", allowed(method, path), False)


check(
    "an issue can be filed, on a human's click",
    allowed("POST", "/repos/o/r/issues"),
    True,
)

for payload, what in (
    ({"title": "x", "assignees": ["someone"]}, "assigning someone"),
    ({"title": "x", "labels": ["urgent"]}, "labelling it"),
    ({"body": "no title"}, "an issue without a title"),
):

    try:
        github.GitHubService("o", "r", token="tok")._request(
            "POST",
            "/repos/o/r/issues",
            payload,
        )

        check(f"{what} on a new issue is refused", "sent", "refused")

    except github.GitHubError:
        check(f"{what} on a new issue is refused", "refused", "refused")


check(
    "a pull request's title and body can be rewritten",
    allowed("PATCH", "/repos/o/r/pulls/17"),
    True,
)

for payload, what in (
    ({"state": "closed"}, "closing a pull request"),
    ({"base": "release"}, "retargeting a pull request"),
    ({"title": "x", "state": "closed"}, "closing one under a new title"),
):

    try:
        github.GitHubService("o", "r", token="tok")._request(
            "PATCH",
            "/repos/o/r/pulls/17",
            payload,
        )

        check(f"{what} is refused", False, True)

    except GitHubError:
        check(f"{what} is refused", True, True)


class FakeResponse:
    def __init__(self, status: int, payload=None) -> None:
        self.status_code = status
        self._payload = payload if payload is not None else {}
        self.headers = {}
        self.content = b"x"
        self.text = str(self._payload)

    def json(self):
        return self._payload


CALLS: list[tuple[str, str]] = []

PULL_REQUEST = {
    "id": 1,
    "number": 17,
    "title": "A pull request",
    "body": "",
    "labels": [],
    "state": "open",
    "html_url": "https://github.com/o/r/pull/17",
    "pull_request": {"url": "..."},
}

ISSUE = {
    "id": 2,
    "number": 18,
    "title": "A real issue",
    "body": "",
    "labels": [],
    "state": "open",
    "html_url": "https://github.com/o/r/issues/18",
}


def fake_request(method: str, url: str, **kwargs):

    path = url.replace(github.API_ROOT, "")

    CALLS.append((method, path))

    if path.endswith("/17"):
        return FakeResponse(200, PULL_REQUEST)

    return FakeResponse(200, ISSUE)


github.requests.request = fake_request

from services.github_issue_service import GitHubIssueService

service = GitHubIssueService("o", "r", token="tok")

# GitHub numbers pull requests in the same sequence as
# issues and serves them from the same endpoint, so the
# allow list cannot tell them apart. Only reading can.
CALLS.clear()

refuses(
    "closing a pull request through the issues endpoint",
    lambda: service.close_issue(17),
)

check(
    "and nothing was written while finding out",
    [method for method, _ in CALLS],
    ["GET"],
)

CALLS.clear()

service.close_issue(18)

check(
    "a real issue can still be closed deliberately",
    [method for method, _ in CALLS],
    ["GET", "PATCH"],
)

for payload in (
    {"title": "rewritten"},
    {"body": "rewritten"},
    {"state": "closed", "title": "sneaked in"},
):
    refuses(
        f"a PATCH carrying {sorted(payload)}",
        lambda body=payload: service._request(
            "PATCH",
            "/repos/o/r/issues/18",
            body,
        ),
    )

print()
print("=" * 80)
print("NOTHING REACHES GIT WITHOUT AN APPROVAL FIRST")
print("=" * 80)

from agents.git_agent import GitAgent
from models.file_generation_result import (
    FileGenerationResult,
)
from models.file_type import FileType
from models.task import Task
from models.task_status import TaskStatus

for status in (
    TaskStatus.WAITING_FOR_APPROVAL,
    TaskStatus.REJECTED,
):
    allowed_to_commit, reason = GitAgent.can_commit(
        Task(
            repository_path=sandbox,
            status=status,
        )
    )

    check(
        f"a {status.value} task is not committed",
        allowed_to_commit,
        False,
    )

    check(
        f"and says why ({status.value})",
        bool(reason),
        True,
    )

approved = Task(
    repository_path=sandbox,
    status=TaskStatus.APPROVED,
    generated_files=[
        FileGenerationResult(
            relative_path="generated.ts",
            content="export class Generated {}",
            file_type=FileType.SOURCE,
        )
    ],
)

check(
    "an approved task with files may be",
    GitAgent.can_commit(approved),
    (True, ""),
)

check(
    "approval alone is not enough without files",
    GitAgent.can_commit(
        Task(
            repository_path=sandbox,
            status=TaskStatus.APPROVED,
        )
    )[0],
    False,
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL GOVERNANCE CHECKS PASSED")
print("=" * 80)
