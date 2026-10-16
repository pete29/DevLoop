import os
import re
from dataclasses import dataclass

from services.git_service import GitService
from services.github_service import (
    GitHubError,
    GitHubService,
    read_token,
)

# GitHub's own rule for a repository name, which also makes
# a safe folder name on every system.
VALID_NAME = re.compile(r"^[A-Za-z0-9._-]{1,100}$")

# A separate, broader token, used only to create a
# repository: creating one needs account-level
# "Administration: write", which the everyday token, scoped
# to the repositories it works on, should not have.
ADMIN_TOKEN_VARIABLE = "GITHUB_ADMIN_PAT"

BASE_BRANCH = "main"


def pick_folder(start: str = "") -> str:
    """The system's own "choose a folder" window, or "".

    The app runs on the user's machine, so a native dialog
    is possible and beats typing a path. Opened and closed
    in one call, on top of the browser; "" when cancelled
    or when there is no display to show it on.
    """

    try:
        import tkinter
        from tkinter import filedialog

        root = tkinter.Tk()

        root.withdraw()

        root.attributes("-topmost", True)

        chosen = filedialog.askdirectory(
            parent=root,
            initialdir=start or os.path.expanduser("~"),
            mustexist=True,
        )

        root.destroy()

    except Exception as error:
        print(f"no folder dialog: {error}")

        return ""

    return os.path.normpath(chosen) if chosen else ""


def folder_name(path: str) -> str:
    """The name a registered repository gets: its folder's."""

    return os.path.basename(os.path.normpath(path or "")) if path else ""


def git_root(path: str) -> str:
    """The folder holding the repository `path` is in, or "".

    Read from the folders, not from git: the form asks on
    every keystroke.
    """

    if not path:
        return ""

    current = os.path.abspath(path)

    while True:

        if os.path.exists(os.path.join(current, ".git")):
            return current

        parent = os.path.dirname(current)

        if parent == current:
            return ""

        current = parent


def check_existing(path: str) -> tuple[str, str]:
    """Whether a folder can be registered as it is.

    ("", "") when it can; otherwise a reason -- "missing",
    "not_git" or "inside" -- and, for "inside", the
    repository's own folder. A folder without git cannot
    have a branch, so nothing could run in it; a folder
    inside a repository would read only part of it.
    """

    if not path or not os.path.isdir(path):
        return "missing", ""

    root = git_root(path)

    if not root:
        return "not_git", ""

    if os.path.normcase(root) != os.path.normcase(os.path.abspath(path)):
        return "inside", root

    return "", ""


def start_git(path: str) -> None:
    """Makes an existing folder a repository, on main."""

    GitService(path).init(BASE_BRANCH)


def admin_token() -> str:

    return (os.getenv(ADMIN_TOKEN_VARIABLE) or "").strip() or read_token()


@dataclass
class Created:
    """What creating a repository produced."""

    path: str

    html_url: str = ""

    clone_url: str = ""

    # Why the everyday token cannot work on it, or "".
    access: str = ""


def everyday_access(html_url: str, token: str | None = None, admin: str | None = None) -> str:
    """Why the everyday token cannot reach a new repository, or "".

    The admin token creates it; the everyday one, scoped to
    chosen repositories, pushes and opens pull requests. A
    new repository is outside that scope until someone adds
    it, and on csv-kit that surfaced only at the first push,
    after a paid run.
    """

    token = read_token() if token is None else token

    admin = admin_token() if admin is None else admin

    # One token for both: it just created the repository.
    if not html_url or not token or token == admin:
        return ""

    try:
        service = GitHubService.from_remote(html_url, token=token)

        data = service._request("GET", f"/repos/{service.owner}/{service.repository}")

    except GitHubError as error:
        return (
            f"GITHUB_PAT cannot see {html_url} ({error}). Add the repository "
            "to the token's repository access on GitHub (Settings → Developer "
            "settings → Fine-grained tokens), with Contents and Pull requests: "
            "read and write, before the first run."
        )

    permissions = data.get("permissions")

    if isinstance(permissions, dict) and permissions.get("push") is False:
        return f"GITHUB_PAT can read {html_url} but not push to it."

    return ""


def check_new(parent: str, name: str) -> str:
    """Why a new repository cannot be made here, or ""."""

    if not VALID_NAME.match(name or "") or name in (".", ".."):
        return (
            "Use letters, digits, '.', '-' and '_' only, as "
            "GitHub does."
        )

    if not parent or not os.path.isdir(parent):
        return f"The parent folder does not exist: {parent}"

    if os.path.exists(os.path.join(parent, name)):
        return f"{os.path.join(parent, name)} already exists."

    return ""


def create(
    parent: str,
    name: str,
    on_github: bool,
    private: bool = True,
    description: str = "",
) -> Created:
    """A new repository: a folder with git, and on GitHub too.

    GitHub first: if it refuses, nothing is left behind
    locally. It is created with a first commit, because an
    empty repository has no main, the factory never pushes
    to main, and a pull request needs a base. The local
    side is then a clone made of allowed steps -- init,
    add origin, fetch, check out main -- since clone itself
    is not on the git allow list.
    """

    problem = check_new(parent, name)

    if problem:
        raise ValueError(problem)

    target = os.path.join(parent, name)

    created = Created(path=target)

    if on_github:

        data = GitHubService("", "", token=admin_token())._request(
            "POST",
            "/user/repos",
            payload={
                "name": name,
                "private": bool(private),
                "description": description.strip(),
                "auto_init": True,
            },
        )

        created.html_url = str(data.get("html_url") or "")

        created.clone_url = str(data.get("clone_url") or "")

        if not created.clone_url:
            raise GitHubError("GitHub did not return the new repository's URL.")

    os.makedirs(target)

    service = GitService(target)

    service.init(BASE_BRANCH)

    if created.clone_url:

        service.add_origin(created.clone_url)

        service.fetch("origin")

        service.checkout_new_branch(
            BASE_BRANCH,
            f"origin/{BASE_BRANCH}",
            strict=True,
        )

        created.access = everyday_access(created.html_url)

    return created
