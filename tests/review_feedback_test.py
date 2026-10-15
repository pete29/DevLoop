"""Offline checks for review comments read from a pull request.

GitHub is faked; nothing is written to it:

    python -m tests.review_feedback_test
"""

import os
import shutil
import tempfile

folder = tempfile.mkdtemp()

os.environ["DEVLOOP_DATABASE"] = os.path.join(folder, "feedback.db")
os.environ.setdefault("GITHUB_PAT", "ghp_faketoken")

import services.github_service as github  # noqa: E402
from database.plan_repository import PlanRepository  # noqa: E402
from models.file_type import FileType  # noqa: E402
from models.generated_file import GeneratedFile  # noqa: E402
from models.plan import Plan  # noqa: E402
from models.task import Task  # noqa: E402
from services import review_feedback  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


INLINE = [
    {
        "id": 11,
        "path": "src/lowercase-rule.ts",
        "line": 14,
        "body": "Return the message from a field, like UppercaseRule does.",
        "user": {"login": "reviewer"},
        "html_url": "https://github.com/o/r/pull/8#discussion_r11",
        "created_at": "2026-10-15T10:02:00Z",
    }
]

REVIEWS = [
    {"id": 21, "body": "", "state": "APPROVED", "user": {"login": "reviewer"}, "submitted_at": "2026-10-15T10:00:00Z"},
    {
        "id": 22,
        "body": "Please also cover an empty password.",
        "state": "CHANGES_REQUESTED",
        "user": {"login": "reviewer"},
        "html_url": "https://github.com/o/r/pull/8#pullrequestreview-22",
        "submitted_at": "2026-10-15T10:03:00Z",
    },
]

CONVERSATION = [
    {"id": 31, "body": "**DevLoop** ran this task.", "user": {"login": "pete29"}, "created_at": "2026-10-15T09:00:00Z"},
    {
        "id": 32,
        "body": "Looks good otherwise!",
        "user": {"login": "lead"},
        "html_url": "https://github.com/o/r/pull/8#issuecomment-32",
        "created_at": "2026-10-15T10:01:00Z",
    },
]

CALLS: list[tuple[str, str]] = []


class FakeResponse:
    def __init__(self, data):
        self.status_code = 200
        self.content = b"x"
        self._data = data

    def json(self):
        return self._data


def fake_request(method, url, **kwargs):

    path = url.replace(github.API_ROOT, "")

    CALLS.append((method, path))

    if path.endswith("/pulls/8/comments"):
        return FakeResponse(INLINE)

    if path.endswith("/pulls/8/reviews"):
        return FakeResponse(REVIEWS)

    if path.endswith("/issues/8/comments"):
        return FakeResponse(CONVERSATION)

    return FakeResponse([])


github.requests.request = fake_request

try:

    print("=" * 80)
    print("WHAT REVIEWERS SAID, AND NOTHING ELSE")
    print("=" * 80)

    service = github.GitHubService("o", "r", token="tok")

    found = review_feedback.read(service, 8)

    check(
        "inline comments, review text and the conversation, oldest first",
        [comment.key for comment in found],
        ["comment:32", "inline:11", "review:22"],
    )

    check(
        "a bare approval and DevLoop's own comment are left out",
        any(comment.key in ("review:21", "comment:31") for comment in found),
        False,
    )

    check(
        "only reads were sent",
        {method for method, _ in CALLS},
        {"GET"},
    )

    inline = found[1]

    check("an inline comment knows its file and line", inline.where, "src/lowercase-rule.ts:14")

    check(
        "and becomes a note that says where and who",
        inline.as_note(),
        "PR review comment on src/lowercase-rule.ts:14 by reviewer: "
        "Return the message from a field, like UppercaseRule does.",
    )

    print()
    print("=" * 80)
    print("WHICH TASK A COMMENT IS ABOUT")
    print("=" * 80)

    def record(record_id, path, at):
        return Task(
            id=record_id,
            created_at=at,
            generated_files=[GeneratedFile(path, FileType.SOURCE)],
        )

    records = [
        record("rule-v1", "src/lowercase-rule.ts", "2026-10-15T09:00:00+00:00"),
        record("rule-v2", "src/lowercase-rule.ts", "2026-10-15T09:30:00+00:00"),
        record("strength", "src/password-strength.ts", "2026-10-15T09:40:00+00:00"),
    ]

    check("the latest record that wrote the file", review_feedback.owner_of(inline, records), "rule-v2")

    check("a general comment names none", review_feedback.owner_of(found[0], records), "")

    check(
        "several comments become one note per line",
        len(review_feedback.notes(found).splitlines()),
        3,
    )

    print()
    print("=" * 80)
    print("READING IS ALLOWED, WRITING ON THE REQUEST IS NOT")
    print("=" * 80)

    for method, path in (
        ("POST", "/repos/o/r/pulls/8/comments"),
        ("POST", "/repos/o/r/pulls/8/reviews"),
        ("PATCH", "/repos/o/r/pulls/comments/11"),
        ("DELETE", "/repos/o/r/issues/comments/32"),
    ):
        try:
            service._request(method, path, {"body": "x"})
            check(f"{method} {path} is refused", "sent", "refused")

        except github.GitHubError:
            check(f"{method} {path} is refused", "refused", "refused")

    print()
    print("=" * 80)
    print("A COMMENT SENT BACK IS NOT OFFERED AGAIN")
    print("=" * 80)

    plans = PlanRepository()

    plan = Plan(epic="Epic")

    plans.save(plan)

    plans.mark_acted(plan.id, ["inline:11"])

    acted = plans.mark_acted(plan.id, ["inline:11", "review:22"])

    check("recorded once each", acted, ["inline:11", "review:22"])

    check("and stored with the plan", plans.get_by_id(plan.id).acted_comments, ["inline:11", "review:22"])

    plans.connection.close()

finally:
    shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL REVIEW FEEDBACK CHECKS PASSED")
print("=" * 80)
