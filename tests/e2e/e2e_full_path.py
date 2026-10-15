"""The whole path, offline: a GitHub issue in, a merged pull request out.

Issue → requirement → plan → background run → review of each
task → commit → push → pull request → merged → delivered,
driven through the real page (rendered headlessly) the way a
person clicks it. Real: the page, the orchestrator and its
checks, git, SQLite, the worker's loop, the HTTP calls to
GitHub. Scripted: the model's answers. Faked: GitHub itself,
a server on localhost; the remote is a bare repository on
disk standing in for github.com.

The compiler and test runner are borrowed from a project
that has them (see conftest.py); without one the gates are
reported unavailable and the path still has to complete.
"""

import os
import subprocess

import pytest
from conftest import find_typescript, link, unlink
from fake_github import FakeGitHub
from scripted_model import ScriptedModel

pytestmark = pytest.mark.e2e

OWNER, NAME = "e2e-owner", "datepicker"

REMOTE = f"https://github.com/{OWNER}/{NAME}.git"


def git(cwd, *args: str) -> str:

    return subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def button(at, key: str):

    found = [item for item in at.button if item.key == key]

    assert found, f"no button {key!r} on the page"

    return found[0]


def labelled(at, label: str):

    found = [item for item in at.button if item.label == label]

    assert found, f"no button labelled {label!r} on the page"

    return found[0]


def no_errors(at) -> None:

    assert [item.value for item in at.exception] == []


@pytest.fixture
def project(workspace):
    """A TypeScript project on main, its origin a bare repository."""

    bare = workspace / "origin.git"

    root = workspace / NAME

    subprocess.run(["git", "init", "--quiet", "--bare", "--initial-branch=main", str(bare)], check=True)

    subprocess.run(["git", "init", "--quiet", "--initial-branch=main", str(root)], check=True)

    git(root, "config", "user.email", "e2e@example.com")
    git(root, "config", "user.name", "E2E")

    # DevLoop reads owner and repository from a github.com
    # URL; git is told that URL means the bare repository.
    git(root, "remote", "add", "origin", REMOTE)
    git(root, "config", f"url.{bare.as_uri()}.insteadOf", REMOTE)

    from services.environment_step import write_scaffolding

    write_scaffolding(str(root))

    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "chore: project scaffolding")
    git(root, "push", "--quiet", "origin", "main")

    modules = find_typescript()

    if modules:
        link(modules, str(root / "node_modules"))

    yield root, bare, bool(modules)

    unlink(str(root / "node_modules"))


def test_an_issue_becomes_a_merged_pull_request(project, monkeypatch):

    root, bare, compiler = project

    from database.repository_repository import RepositoryRepository
    from database.requirement_repository import RequirementRepository
    from database.run_repository import RunRepository
    from database.plan_repository import PlanRepository
    from database.task_repository import TaskRepository
    from models.repository import Repository
    from models.task_status import TaskStatus
    from services import github_service, plan_runner
    from services.translations import translate
    import services.llm_factory as factory
    from streamlit.testing.v1 import AppTest
    from workflows.workflow_orchestrator import WorkflowOrchestrator

    prompts: list[tuple[str, str]] = []

    monkeypatch.setattr(factory.LLMFactory, "create", classmethod(lambda cls, role="": ScriptedModel(role, prompts)))

    # The worker would be a separate process; here it runs
    # in this one, to the end, when the run is started.
    monkeypatch.setattr(
        plan_runner,
        "spawn_worker",
        lambda run: plan_runner.work(run.id, RunRepository(), PlanRepository(), TaskRepository(), WorkflowOrchestrator()),
    )

    # git sends everything to the bare repository (insteadOf),
    # and so reports its path as origin's URL; DevLoop is
    # shown the github.com address it would see for real.
    from services.git_service import GitService

    real_remote_url = GitService.remote_url

    monkeypatch.setattr(
        GitService,
        "remote_url",
        lambda self, *args, **kwargs: REMOTE if os.path.samefile(self.repository_path, root) else real_remote_url(self, *args, **kwargs),
    )

    repository = Repository(name=NAME, path=str(root))

    RepositoryRepository().save(repository)

    with FakeGitHub(OWNER, NAME) as github:

        monkeypatch.setattr(github_service, "API_ROOT", github.url)

        issue = github.add_issue("Calendar date arithmetic", "Add days to a date, and tell its weekday.")

        app = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "app.py")

        at = AppTest.from_file(app, default_timeout=120)

        at.session_state.repository_id = repository.id

        at.run()

        no_errors(at)

        # ------------------------------------------------ the issue becomes a requirement


        button(at, f"issue-{issue['number']}").click().run()

        no_errors(at)

        requirement = RequirementRepository().get_by_issue(issue["number"])

        assert requirement is not None and requirement.repository_id == repository.id

        # ------------------------------------------------ the planner plans it

        labelled(at, translate("requirement.generate_plan", "en")).click().run()

        no_errors(at)

        plan = PlanRepository().get_all()[0]

        assert [item.title for item in plan.tasks] == ["Add day arithmetic", "Add the weekday"]

        assert plan.requirement_id == requirement.id and not plan.issues

        # ------------------------------------------------ the whole plan runs

        if not compiler:
            # Nothing installed to compile or test with: the
            # environment step is skipped, as a person would.
            at.checkbox(key=f"skip-environment-{plan.id}").check().run()

        run_all = [item for item in at.button if item.label.startswith("⏩")]

        assert run_all and not run_all[0].disabled, "Run the whole plan is not offered"

        run_all[0].click().run()

        no_errors(at)

        run = RunRepository().latest(plan.id)

        assert run.status.value == "DONE", run.message

        records = [TaskRepository().get_by_id(record_id) for record_id in run.produced]

        assert [record.status for record in records] == [TaskStatus.WAITING_FOR_APPROVAL] * 2

        assert all(record.recommendation.value == "APPROVE" for record in records), [r.recommendation for r in records]

        branch = records[0].branch

        assert branch.startswith(f"feature/issue-{issue['number']}-")

        assert (root / "src" / "days.ts").exists() and (root / "src" / "weekday.ts").exists()

        assert not list(root.glob("*.js")), "a compiled-name import made a copy"

        if compiler:
            assert all(record.compile_result.status.value == "PASSED" for record in records)
            assert all(record.test_result.status.value == "PASSED" for record in records)

        # ------------------------------------------------ each task is reviewed and accepted

        for item in plan.tasks:

            at.session_state.plan = PlanRepository().get_by_id(plan.id)

            at.run()

            button(at, f"open-task-{plan.id}-{item.id}").click().run()

            labelled(at, translate("task.approve", "en")).click().run()

            no_errors(at)

        committed = [TaskRepository().get_by_id(record.id) for record in records]

        assert all(record.git_operation.committed for record in committed)

        assert git(root, "rev-parse", "--abbrev-ref", "HEAD") == branch

        assert len(git(root, "log", "--format=%h", f"main..{branch}").split()) == 2

        # ------------------------------------------------ pushed, and a pull request opened

        labelled(at, translate("git.push", "en")).click().run()

        no_errors(at)

        assert git(bare, "rev-parse", branch) == git(root, "rev-parse", branch)

        at.session_state.task = TaskRepository().get_by_id(records[-1].id)

        at.run()

        labelled(at, translate("pr.create", "en")).click().run()

        no_errors(at)

        assert len(github.pulls) == 1

        pull = next(iter(github.pulls.values()))

        assert pull["head"]["ref"] == branch and pull["base"]["ref"] == "main"

        assert "Add day arithmetic" in pull["body"] and "Add the weekday" in pull["body"]

        assert github.comments.get(issue["number"]), "the issue was not told about the pull request"

        # ------------------------------------------------ merged on GitHub, read back as delivered

        github.merge(pull["number"])

        git(bare, "update-ref", "refs/heads/main", git(bare, "rev-parse", branch))

        at.session_state.task = None

        at.session_state.plan = PlanRepository().get_by_id(plan.id)

        at.session_state.requirement = RequirementRepository().get_by_id(requirement.id)

        at.run()

        button(at, f"pr-refresh-{plan.id}").click().run()

        no_errors(at)

        assert all(TaskRepository().get_by_id(record.id).pull_request.state.value == "MERGED" for record in records)

        at.run()

        status = " ".join(item.value for item in at.caption)

        assert "DELIVERED" in status, status

        # ------------------------------------------------ what it all cost

        roles = [role for role, _ in prompts]

        assert roles.count("planner") == 1

        assert roles.count("architect") == 2, "one review per task, no fix rounds"

        assert "github.com" not in " ".join(github.calls)
