import os
from dataclasses import dataclass, field

from services.bootstrap import TEMPLATES, bootstrap
from services.git_service import GitError, GitService
from services.package_installer import blocked
from services.repository_context import describe
from services.type_checker import tsc_entry

# What npm install writes next to package.json. Committed
# with the scaffolding, so every clone installs the same
# versions the tests ran against.
LOCK_FILE = "package-lock.json"

COMMIT_MESSAGE = (
    "chore: project scaffolding\n\n"
    "Written from templates by DevLoop before the "
    "first task, so every task branch starts from a "
    "project that builds."
)


@dataclass
class EnvironmentStep:
    """Step 0 of every plan: what the repository still lacks.

    Every field is read off disk and out of git, never
    asked of a model and never stored -- the same reason
    RepositoryContext is derived. It was all true before
    this existed, but it lived beside the plan as a few
    captions: the plan's progress said nothing about it,
    and "run the whole plan" started the first task in a
    folder that could neither compile nor test what it was
    about to pay for.
    """

    # Scaffolding files that do not exist yet.
    missing: list[str] = field(default_factory=list)

    # Scaffolding that exists but git does not track: it
    # would be missing from every branch and pull request.
    uncommitted: list[str] = field(default_factory=list)

    # TypeScript and Vitest are not installed, so nothing
    # can be compiled or tested.
    dependencies_missing: bool = False

    # Why installing cannot run here, or ''.
    install_blocked: str = ""

    git: bool = False

    # git has no user.name or user.email, here or globally:
    # every commit would be refused.
    identity_missing: bool = False

    base_branch: str = ""

    @property
    def ready(self) -> bool:

        return (
            self.git
            and not self.identity_missing
            and not self.missing
            and not self.uncommitted
            and not self.dependencies_missing
        )


def assess(repository_path: str) -> EnvironmentStep:

    step = EnvironmentStep()

    if not repository_path or not os.path.isdir(
        repository_path
    ):
        return step

    context = describe(repository_path)

    step.missing = [
        name for name in context.missing if name in TEMPLATES
    ]

    step.dependencies_missing = not (
        tsc_entry(repository_path)
        and os.path.isdir(
            os.path.join(
                repository_path, "node_modules", "vitest"
            )
        )
    )

    # Only once there is something to install. With the
    # scaffolding missing, the reason would be "no
    # package.json", which is the line above, not this one.
    if not step.missing:
        step.install_blocked = blocked(repository_path)

    service = GitService(repository_path)

    step.git = service.is_repository()

    if step.git:

        step.identity_missing = not all(service.identity())

        step.base_branch = service.base_branch()

        step.uncommitted = untracked(
            service,
            [
                name
                for name in (*TEMPLATES, LOCK_FILE)
                if os.path.isfile(
                    os.path.join(repository_path, name)
                )
            ],
        )

    return step


def untracked(
    service: GitService,
    paths: list[str],
) -> list[str]:
    """The paths not in any commit yet, staged or not."""

    committed = service.committed(paths)

    return [path for path in paths if path not in committed]


def write_scaffolding(repository_path: str) -> list[str]:
    """The templates for whatever is missing, nothing else."""

    return bootstrap(
        repository_path,
        describe(repository_path),
    )


def commit_scaffolding(repository_path: str) -> str:
    """Commits the scaffolding on the base branch.

    On the base branch, not a task branch, because every
    task branch is cut from there: committed on the first
    task's branch, the second task's branch would start
    without a package.json. Exactly the scaffolding files
    are staged, by name -- never the whole tree.

    Called from a button, which is the approval: nothing
    here commits on its own.
    """

    service = GitService(repository_path)

    service.require_repository()

    paths = assess(repository_path).uncommitted

    if not paths:
        raise GitError("There is no scaffolding to commit.")

    base = service.base_branch()

    # A repository with no commit has no base branch yet;
    # this commit is what creates it.
    if base and service.current_branch() != base:
        service.checkout_new_branch(base)

    service.add(paths)

    return service.commit(COMMIT_MESSAGE)
