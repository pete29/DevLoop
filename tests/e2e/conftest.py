"""Setup shared by the end-to-end tests.

Run before any DevLoop module is imported: the database a
process uses is read once, at import, so it is pointed at a
throwaway file here, never at the real one. Keys are blanked
for the same reason -- nothing here may reach a real service.
"""

import os
import sys
import tempfile

WORKSPACE = tempfile.mkdtemp(prefix="devloop-e2e-")

os.environ["DEVLOOP_DATABASE"] = os.path.join(WORKSPACE, "e2e.db")
os.environ["DEVLOOP_NOTIFY"] = "0"
os.environ["DEVLOOP_PASSWORD_HASH"] = ""
os.environ["DEVLOOP_MONTH_LIMIT"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
os.environ["GITHUB_ADMIN_PAT"] = ""
os.environ["GITHUB_PAT"] = "github_pat_fake_for_the_e2e_tests"

import pytest  # noqa: E402


def installed(folder: str) -> bool:

    modules = os.path.join(folder, "node_modules")

    return os.path.isfile(os.path.join(modules, "typescript", "lib", "tsc.js")) and os.path.isdir(
        os.path.join(modules, "vitest")
    )


def find_typescript() -> str:
    """A node_modules with TypeScript and Vitest to borrow, or "".

    DEVLOOP_TYPESCRIPT_HOME names a project that has both;
    otherwise a sibling folder of this repository is looked
    for. Without one, the tests run with the compiler and
    the test runner reported unavailable, as on a machine
    where nothing is installed yet.
    """

    named = os.getenv("DEVLOOP_TYPESCRIPT_HOME", "")

    if named:
        return os.path.join(named, "node_modules") if installed(named) else ""

    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    parent = os.path.dirname(here)

    for name in sorted(os.listdir(parent)):

        candidate = os.path.join(parent, name)

        if candidate != here and os.path.isdir(candidate) and installed(candidate):
            return os.path.join(candidate, "node_modules")

    return ""


def link(target: str, link_path: str) -> None:
    """Borrowed, not copied: a junction on Windows, a symlink elsewhere."""

    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(target, link_path)

    else:
        os.symlink(target, link_path, target_is_directory=True)


def unlink(link_path: str) -> None:
    """Removes the link only, never what it points at."""

    if os.path.lexists(link_path):
        os.rmdir(link_path) if sys.platform == "win32" else os.unlink(link_path)


@pytest.fixture
def workspace(tmp_path):

    return tmp_path
