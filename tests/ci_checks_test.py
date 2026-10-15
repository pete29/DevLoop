"""Offline checks for reading a pull request's CI.

GitHub is faked; nothing is written to it:

    python -m tests.ci_checks_test
"""

import os

os.environ.setdefault("GITHUB_PAT", "ghp_faketoken")

import services.github_service as github  # noqa: E402
from services import ci_checks  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


SHA = "c8b1bc8df716fb52b45e0445f39f79ce711246fa"

LOG = "\n".join(f"line {n}" for n in range(1, 101)) + "\n FAIL tests/x.test.ts > rejects\nError: Process completed with exit code 1.\n"

CALLS: list[tuple[str, str]] = []


class FakeResponse:
    def __init__(self, data=None, text=""):
        self.status_code = 200
        self.content = b"x"
        self._data = data
        self.text = text

    def json(self):
        return self._data


def fake_request(method, url, **kwargs):

    path = url.replace(github.API_ROOT, "")

    CALLS.append((method, path))

    if path == "/repos/o/r/pulls/8":
        return FakeResponse({"head": {"sha": SHA}})

    if path == "/repos/o/r/actions/runs":
        assert kwargs.get("params", {}).get("head_sha") == SHA
        return FakeResponse({"workflow_runs": [{"id": 70}, {"id": 71}]})

    if path == "/repos/o/r/actions/runs/70/jobs":
        return FakeResponse(
            {
                "jobs": [
                    {"id": 1, "name": "lint", "status": "completed", "conclusion": "success", "html_url": "u1"},
                    {"id": 2, "name": "test", "status": "completed", "conclusion": "failure", "html_url": "u2",
                     "steps": [{"name": "Install", "conclusion": "success"}, {"name": "Run vitest", "conclusion": "failure"}]},
                ]
            }
        )

    if path == "/repos/o/r/actions/runs/71/jobs":
        return FakeResponse(
            {
                "jobs": [
                    {"id": 3, "name": "build", "status": "in_progress", "conclusion": None, "html_url": "u3"},
                    {"id": 4, "name": "expired", "status": "completed", "conclusion": "failure",
                     "steps": [{"name": "Compile", "conclusion": "failure"}]},
                ]
            }
        )

    if path == "/repos/o/r/actions/jobs/2/logs":
        return FakeResponse(text=LOG)

    if path == "/repos/o/r/actions/jobs/4/logs":  # expired
        response = FakeResponse({"message": "Not Found"})
        response.status_code = 404
        return response

    return FakeResponse({})


github.requests.request = fake_request

service = github.GitHubService("o", "r", token="tok")

print("=" * 80)
print("THE CHECKS OF THE REQUEST'S HEAD")
print("=" * 80)

head, runs = ci_checks.read(service, 8)

check("read for the head commit", head, SHA)

check("jobs of every run, failures first", [run.name for run in runs], ["expired", "test", "build", "lint"])

check("each marked", [run.mark for run in runs], ["❌", "❌", "⏳", "✅"])

test_run = runs[1]

tail = ci_checks.log_tail(service, test_run)

check(
    "a failed job's log, its end",
    (len(tail.splitlines()), tail.splitlines()[-1]),
    (60, "Error: Process completed with exit code 1."),
)

check(
    "a log that cannot be read falls back to the steps that failed",
    ci_checks.log_tail(service, runs[0]),
    "Compile",
)

note = ci_checks.as_note(test_run, tail)

check(
    "and becomes a revision note naming the check",
    (note.startswith("The pull request's CI check 'test' failed (failure)."), "FAIL tests/x.test.ts" in note),
    (True, True),
)

check("only reads were sent", {method for method, _ in CALLS}, {"GET"})

print()
print("=" * 80)
print("NOTHING IS RE-RUN OR CHANGED")
print("=" * 80)

for method, path in (
    ("POST", "/repos/o/r/actions/jobs/2/rerun"),
    ("POST", "/repos/o/r/check-runs/2/rerequest"),
    ("POST", "/repos/o/r/actions/runs/9/cancel"),
    ("PATCH", "/repos/o/r/check-runs/2"),
    ("GET", "/repos/o/r/commits/main/check-runs"),
):
    try:
        service._request(method, path)
        check(f"{method} {path} is refused", "sent", "refused")

    except github.GitHubError:
        check(f"{method} {path} is refused", "refused", "refused")

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL CI CHECKS PASSED")
print("=" * 80)
