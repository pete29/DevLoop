"""The CI on a plan's pull request, read only.

DevLoop's own gates compile and test in the working folder;
the target repository may run more on GitHub (a linter, a
build, another test suite) and that verdict never reached
the plan. This reads the GitHub Actions jobs of the
request's head commit and, for a failed one, the end of its
log -- what a human reads to see why -- so a failure can be
sent back to a task like a review comment.

Through the Actions API: a fine-grained token cannot hold the
Checks permission, and Actions: read is all this needs.
Nothing is re-run, cancelled or written.
"""

from dataclasses import dataclass

from services.github_service import GitHubError, GitHubService

# A failure's cause is near the end of a job's log.
LOG_TAIL_LINES = 60

FAILED = frozenset({"failure", "timed_out", "cancelled", "action_required", "startup_failure"})


@dataclass
class CheckRun:

    id: int

    name: str

    # queued, in_progress or completed
    status: str = ""

    # success, failure, neutral, skipped, ... once completed
    conclusion: str = ""

    url: str = ""

    summary: str = ""

    @property
    def failed(self) -> bool:

        return self.status == "completed" and self.conclusion in FAILED

    @property
    def mark(self) -> str:

        if self.status != "completed":
            return "⏳"

        if self.failed:
            return "❌"

        return "✅" if self.conclusion == "success" else "➖"


def read(service: GitHubService, number: int) -> tuple[str, list[CheckRun]]:
    """The request's head commit and its Actions jobs."""

    head = (service.read_pull_request(number).get("head") or {}).get("sha", "")

    if not head:
        return "", []

    runs = [
        CheckRun(
            id=int(item.get("id") or 0),
            name=item.get("name") or "",
            status=item.get("status") or "",
            conclusion=item.get("conclusion") or "",
            url=item.get("html_url") or "",
            summary=", ".join(
                step.get("name", "")
                for step in item.get("steps") or []
                if step.get("conclusion") in FAILED
            ),
        )
        for item in service.list_jobs(head)
    ]

    return head, sorted(runs, key=lambda run: (not run.failed, run.name))


def log_tail(service: GitHubService, run: CheckRun, lines: int = LOG_TAIL_LINES) -> str:
    """The last lines of a failed job's log, or its failed steps.

    A log that cannot be read (expired, or no access) leaves
    the names of the steps that failed.
    """

    try:
        text = service.job_log(run.id)

    except GitHubError:
        return run.summary

    kept = [line.rstrip() for line in text.splitlines() if line.strip()]

    return "\n".join(kept[-lines:])


def as_note(run: CheckRun, tail: str) -> str:
    """A failed check as a revision note."""

    return (
        f"The pull request's CI check '{run.name}' failed ({run.conclusion}). "
        "Make it pass. The end of its log:\n" + tail
    )
