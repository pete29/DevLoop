"""Offline checks for adding and creating repositories.

Real git in throwaway folders; GitHub is faked, with a
local bare repository standing in for the one it creates:

    python -m tests.repository_setup_test
"""

import os
import shutil
import subprocess
import tempfile

os.environ.setdefault("GITHUB_PAT", "ghp_faketoken")

import services.github_service as github
import services.repository_setup as setup
from services.git_service import GitError, GitService

failures: list[str] = []

folders: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


def refuses(label: str, call, error=Exception) -> None:

    try:
        call()

    except error:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: was allowed")


def folder() -> str:

    path = tempfile.mkdtemp()

    folders.append(path)

    return path


def git(path: str, *args: str) -> str:

    return subprocess.run(
        ["git", "-C", path, *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


try:

    print("=" * 80)
    print("A FOLDER'S NAME IS THE REPOSITORY'S")
    print("=" * 80)

    check(
        "the last segment, whatever the separator",
        (
            setup.folder_name("C:\\Projects\\hitl-sandbox"),
            setup.folder_name("C:/Projects/hitl-sandbox/"),
            setup.folder_name(""),
        ),
        ("hitl-sandbox", "hitl-sandbox", ""),
    )

    parent = folder()

    os.makedirs(os.path.join(parent, "taken"))

    check("a good name in a real folder passes", setup.check_new(parent, "new-repo"), "")

    check(
        "a name GitHub would refuse is refused",
        bool(setup.check_new(parent, "bad name!")),
        True,
    )

    check(
        "so is a folder that already exists",
        "already exists" in setup.check_new(parent, "taken"),
        True,
    )

    check(
        "and a parent that does not",
        "does not exist" in setup.check_new(os.path.join(parent, "nope"), "x"),
        True,
    )

    print()
    print("=" * 80)
    print("A NEW REPOSITORY, LOCAL ONLY")
    print("=" * 80)

    made = setup.create(parent, "local-only", on_github=False)

    check("its folder exists", os.path.isdir(made.path), True)

    check(
        "it is a repository on main",
        git(made.path, "symbolic-ref", "--short", "HEAD"),
        "main",
    )

    check("with no remote", git(made.path, "remote"), "")

    refuses(
        "git init again is refused",
        lambda: GitService(made.path).init("main"),
        GitError,
    )

    print()
    print("=" * 80)
    print("A NEW REPOSITORY, ON GITHUB TOO")
    print("=" * 80)

    # What GitHub creates with auto_init: a repository with
    # one commit on main.
    remote = os.path.join(folder(), "remote.git")

    git(folder(), "init", "--quiet", "--bare", "--initial-branch=main", remote)

    seed = folder()

    git(seed, "init", "--quiet", "--initial-branch=main")

    git(seed, "-c", "user.name=t", "-c", "user.email=t@e", "commit", "--allow-empty", "-m", "Initial commit")

    git(seed, "push", "--quiet", remote, "main")

    SENT: list[tuple[str, str, dict | None]] = []

    def fake_request(self, method, path, payload=None, params=None):

        SENT.append((method, path, payload))

        return {
            "html_url": "https://github.com/me/on-github",
            "clone_url": remote,
        }

    original = github.GitHubService._request

    github.GitHubService._request = fake_request

    made = setup.create(parent, "on-github", on_github=True, description=" Demo ")

    github.GitHubService._request = original

    check(
        "GitHub is asked for a private repository with a first commit",
        SENT[-1],
        (
            "POST",
            "/user/repos",
            {"name": "on-github", "private": True, "description": "Demo", "auto_init": True},
        ),
    )

    check("its URL is reported", made.html_url, "https://github.com/me/on-github")

    check("origin is set", git(made.path, "remote", "get-url", "origin"), remote)

    check(
        "main tracks origin/main, so the first plan has a base",
        git(made.path, "rev-parse", "--abbrev-ref", "main@{upstream}"),
        "origin/main",
    )

    refuses(
        "a second origin is refused",
        lambda: GitService(made.path).add_origin("https://github.com/x/y.git"),
        GitError,
    )

    def refused_by_github(method, path, payload=None, params=None):

        raise github.GitHubError("403 Resource not accessible by personal access token")

    github.GitHubService._request = lambda self, *a, **k: refused_by_github(*a, **k)

    refuses(
        "when GitHub refuses, the error comes through",
        lambda: setup.create(parent, "refused", on_github=True),
        github.GitHubError,
    )

    github.GitHubService._request = original

    check(
        "and nothing is left behind locally",
        os.path.exists(os.path.join(parent, "refused")),
        False,
    )

    print()
    print("=" * 80)
    print("ONLY THE SHAPES THAT WERE REVIEWED")
    print("=" * 80)

    service = GitService(folder())

    for label, args in (
        ("init --bare", ("init", "--bare")),
        ("init with a template", ("init", "--quiet", "--template=x")),
        ("init without a branch", ("init", "--quiet")),
        ("remote add under another name", ("remote", "add", "upstream", "https://github.com/o/r.git")),
        ("remote add with credentials", ("remote", "add", "origin", "https://user:tok@github.com/o/r.git")),
        ("remote add with a flag", ("remote", "add", "-f", "origin", "https://github.com/o/r.git")),
        ("remote set-url", ("remote", "set-url", "origin", "https://github.com/o/r.git")),
        ("remote remove", ("remote", "remove", "origin")),
    ):
        refuses(label, lambda a=args: service._run(*a), GitError)

    hub = github.GitHubService("", "", token="tok")

    for label, payload in (
        ("a repository from a template", {"name": "x", "template_repository": "y"}),
        ("a repository in a team", {"name": "x", "team_id": 1}),
        ("a repository without a name", {"private": True}),
    ):
        refuses(
            label,
            lambda p=payload: hub._request("POST", "/user/repos", p),
            github.GitHubError,
        )

    refuses(
        "a repository in an organisation",
        lambda: hub._request("POST", "/orgs/acme/repos", {"name": "x"}),
        github.GitHubError,
    )

finally:
    for path in folders:
        shutil.rmtree(path, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL REPOSITORY SETUP CHECKS PASSED")
print("=" * 80)
