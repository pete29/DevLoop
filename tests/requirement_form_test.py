"""Offline check: a requirement's repository, and saving it from an old page.

The real page, rendered headlessly against a throwaway
database; nothing calls a model or GitHub:

    python -m tests.requirement_form_test
"""

import copy
import os
import shutil
import tempfile

folder = tempfile.mkdtemp()

os.environ["DEVLOOP_DATABASE"] = os.path.join(folder, "requirement.db")

# A password in the developer's .env would stop the page at
# the sign-in screen; set, even empty, .env does not override it.
os.environ["DEVLOOP_PASSWORD_HASH"] = ""

from streamlit.testing.v1 import AppTest  # noqa: E402

from database.repository_repository import RepositoryRepository  # noqa: E402
from database.requirement_repository import RequirementRepository  # noqa: E402
from models.repository import Repository  # noqa: E402
from models.requirement import Requirement  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


def stored() -> Requirement:

    return RequirementRepository().get_by_id(requirement.id)


try:

    first = Repository(name="first", path=os.path.join(folder, "first"))
    second = Repository(name="second", path=os.path.join(folder, "second"))

    for item in (first, second):
        os.makedirs(item.path)
        RepositoryRepository().save(item)

    requirement = Requirement(repository_id=first.id, title="Datepicker", content="A calendar.")

    RequirementRepository().save(requirement)

    app = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")

    at = AppTest.from_file(app, default_timeout=60)

    at.run()

    print("=" * 80)
    print("THE SIDEBAR LISTS THE SELECTED REPOSITORY'S WORK")
    print("=" * 80)

    def listed() -> bool:
        return any(item.key == f"req-{requirement.id}" for item in at.sidebar.button)

    at.session_state.repository_id = second.id

    at.run()

    check("another repository's requirement is not listed", listed(), False)

    at.session_state.repository_id = first.id

    at.run()

    check("its own repository's is", listed(), True)

    [item for item in at.sidebar.button if item.key == f"req-{requirement.id}"][0].click().run()

    check("the page did not fail", [e.value for e in at.exception], [])

    check("it opens", at.session_state.requirement.id, requirement.id)

    print()
    print("=" * 80)
    print("A REQUIREMENT CAN BE MOVED")
    print("=" * 80)

    # A page opened before the move keeps its own copy.
    stale = copy.deepcopy(at.session_state.requirement)

    at.selectbox(key=f"requirement-repository-{requirement.id}").set_value(second.id).run()

    check("the page did not fail", [e.value for e in at.exception], [])

    check("it is stored in the new repository", stored().repository_id, second.id)

    check("which is now the selected one", at.session_state.repository_id, second.id)

    check("and it stays open, listed under its new repository", (at.session_state.requirement.id, listed()), (requirement.id, True))

    print()
    print("=" * 80)
    print("SWITCHING REPOSITORY CLOSES WHAT BELONGS TO ANOTHER")
    print("=" * 80)

    moved = copy.deepcopy(at.session_state.requirement)

    at.selectbox(key="repository_select").set_value(first.id).run()

    check("the page did not fail", [e.value for e in at.exception], [])

    check("the requirement from the other repository is closed", at.session_state.requirement, None)

    at.selectbox(key="repository_select").set_value(second.id).run()

    at.session_state.requirement = moved

    print()
    print("=" * 80)
    print("SAVING FROM AN OLD PAGE DOES NOT UNDO THE MOVE")
    print("=" * 80)

    at.session_state.requirement = stale

    at.run()

    check("the page reads it again from the database", at.session_state.requirement.repository_id, second.id)

    at.session_state.requirement = stale

    at.text_area(key=f"content-{requirement.id}").set_value("A calendar, in TypeScript.")

    [item for item in at.button if item.label in ("💾 Zapisz", "💾 Save", "Zapisz", "Save")][0].click().run()

    check("the page did not fail", [e.value for e in at.exception], [])

    check(
        "the text is saved, the repository kept",
        (stored().content, stored().repository_id),
        ("A calendar, in TypeScript.", second.id),
    )

    print()
    print("=" * 80)
    print("A RELOAD REMEMBERS THE REPOSITORY")
    print("=" * 80)

    at.selectbox(key="repository_select").set_value(first.id).run()

    reloaded = AppTest.from_file(app, default_timeout=60)

    reloaded.run()

    check("a new session starts on the repository chosen last", reloaded.session_state.repository_id, first.id)

finally:
    shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL REQUIREMENT FORM CHECKS PASSED")
print("=" * 80)
