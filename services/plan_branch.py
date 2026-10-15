import re
import unicodedata
from dataclasses import dataclass

from services.git_service import GitService

PREFIX = "feature/plan-"

MAX_SLUG_WORDS = 4


def slug(text: str) -> str:
    """A few ASCII words from the epic, for a readable name.

    Accents are folded rather than dropped: "Walidator
    haseł" becomes walidator-hasel, not walidator-hase.
    """

    folded = (
        unicodedata.normalize("NFKD", text)
        .replace("ł", "l")
        .replace("Ł", "L")
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )

    words = re.findall(r"[a-z0-9]+", folded)

    return "-".join(words[:MAX_SLUG_WORDS])


def name(plan_id: str, epic: str) -> str:
    """The plan's branch: feature/plan-<id>-<words>.

    Derived, not stored on the plan: the same plan always
    gets the same name, so a plan saved before branches
    existed still finds its own.
    """

    words = slug(epic.splitlines()[0] if epic else "")

    return PREFIX + plan_id[:8] + (f"-{words}" if words else "")


@dataclass
class Entered:
    branch: str

    # Where it came from, for the task's steps: a branch
    # cut from a stale base looks exactly like a fresh one
    # unless something says which it was.
    note: str = ""


def enter(repository_path: str, branch: str) -> Entered:
    """Checks the plan's branch out before a task runs.

    Before, not at commit time. The task is generated
    against whatever is checked out, so a branch chosen
    only when committing meant the second task was written
    beside the first task's files and committed onto a
    branch that did not have them.

    Created the first time from the freshest base that
    loses nothing -- see GitService.start_point: after a
    fetch, origin/main if somebody merged work since.
    Strict:
    if the switch is blocked -- uncommitted changes in the
    way -- the task does not run, rather than being
    generated on the wrong code and paid for anyway.
    """

    service = GitService(repository_path)

    service.require_repository()

    if service.current_branch() == branch:
        return Entered(branch)

    if service.branch_exists(branch):
        service.checkout_new_branch(branch, strict=True)

        return Entered(branch, "existing branch")

    start, note = service.start_point()

    service.checkout_new_branch(branch, start, strict=True)

    return Entered(branch, note)
