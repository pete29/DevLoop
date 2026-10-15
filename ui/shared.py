"""What every part of the page shares: the stores, the language, small helpers.

The stores are created once per process. The repository list is read again
on every run of the page (refresh), so modules read it as shared.repositories."""

import streamlit as st
from dotenv import load_dotenv

from database.plan_repository import PlanRepository
from database.preference_repository import PreferenceRepository
from database.repository_repository import RepositoryRepository, same_path
from database.requirement_repository import RequirementRepository
from database.run_repository import RunRepository
from database.task_repository import TaskRepository
from services import costs
from services.file_writer import FileWriter
from services.translations import DEFAULT_LANGUAGE, translate
from workflows.workflow_orchestrator import WorkflowOrchestrator


# Before anything below is built: the model clients read
# ANTHROPIC_API_KEY when they are created.
load_dotenv()

orchestrator = WorkflowOrchestrator()
repository = TaskRepository()
repository_store = RepositoryRepository()
plan_store = PlanRepository()
requirement_store = RequirementRepository()
run_store = RunRepository()
preferences = PreferenceRepository()

# Read again on every run of the page: a repository added on
# one run is listed on the next.
repositories = []
repositories_by_id = {}

month_blocked = False


# What the page remembers between its runs, and what it
# starts as.
SESSION_DEFAULTS = {
    # The task in the window, the plan and requirement shown.
    "task": None,
    "plan": None,
    "requirement": None,
    "repository_id": None,
    # The outcome of the last action, kept across the rerun
    # that follows it so it is actually seen.
    "git_message": None,
    # The background run this page last saw active, so it
    # can tell when that run ends and redraw once.
    "watching_run": None,
    # Open issues, and the remote they came from: Streamlit
    # reruns the script on every click, and without the
    # remote the app would call GitHub on every one.
    "issues": None,
    "issues_from": None,
    "install_output": "",
    "language": DEFAULT_LANGUAGE,
}


def init_session() -> None:
    """Gives every key the page reads its starting value, once."""

    for key, value in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # The repository selected last time, in any session.
    if st.session_state.repository_id is None:
        st.session_state.repository_id = preferences.get("repository_id") or None

    # The language too: a reload used to bring back the default.
    if not st.session_state.get("language_loaded"):
        st.session_state.language = preferences.get("language") or DEFAULT_LANGUAGE
        st.session_state.language_loaded = True


def select_language(language: str) -> None:
    """Switches the interface's language, and remembers it."""

    st.session_state.language = language

    preferences.set("language", language)


def select_repository(repository_id: str) -> None:
    """Selects a repository, and remembers it for the next session."""

    st.session_state.repository_id = repository_id

    preferences.set("repository_id", repository_id or "")


def refresh() -> None:

    global repositories, repositories_by_id, month_blocked

    repositories = repository_store.get_all()

    repositories_by_id = {item.id: item for item in repositories}

    # Read once per run of the page; every button that
    # spends money is disabled while it is true.
    month_blocked = costs.month_over(repository.get_all(), plan_store.get_all())


def repository_path_now() -> str:
    """The selected repository's folder, or ''."""

    selected = repositories_by_id.get(
        st.session_state.get("repository_id")
    )

    return selected.path if selected else ""


def show_files(root: str, files, empty_message: str) -> None:

    if not files:

        st.info(empty_message)

        return

    for generated in files:

        content = file_content(root, generated)

        with st.expander(generated.path, expanded=True):

            if content is None:

                st.warning(t("files.gone"))

            else:

                st.code(content, language="typescript")


def file_content(root: str, generated) -> str | None:
    """The file as it is on disk right now."""

    if not root:
        return None

    return FileWriter.read(root, generated.path)


def t(key: str, **values: object) -> str:
    """One message, in the language this session chose.

    The language lives in session state rather than in a
    module-level variable, so two browsers pointed at the
    same server do not change each other's interface.
    """

    return translate(
        key,
        st.session_state.get(
            "language",
            DEFAULT_LANGUAGE,
        ),
        **values,
    )


def repository_label(task_like) -> str:

    found = resolve_repository(task_like)

    if found is not None:
        return found.name

    if task_like.repository_path:
        return f"{task_like.repository_path} (not registered)"

    if task_like.repository_id:
        return "Deleted repository"

    return "None"


def resolve_repository(task_like):
    """The repository a task belongs to.

    The stored id wins. When that row is gone, the folder
    the files were written to is matched instead, so a
    repository that is removed and added again still
    reconnects to its tasks.
    """

    found = repositories_by_id.get(
        task_like.repository_id
    )

    if found is not None:
        return found

    for candidate in repositories:

        if same_path(candidate.path, task_like.repository_path):
            return candidate

    return None


def in_selected_repository(item) -> bool:
    """Whether a task, plan or requirement belongs to the selected repository.

    The sidebar listed every repository's work under
    whichever one was selected. A requirement with no
    repository yet is shown everywhere, so it can be given
    one.
    """

    selected = st.session_state.get("repository_id")

    if not selected:
        return True

    if hasattr(item, "repository_path"):
        found = resolve_repository(item)
        return found is not None and found.id == selected

    return not item.repository_id or item.repository_id == selected


def show_message() -> None:
    """The outcome of the last action, kept across the rerun
    that follows it. Rendered at the top rather than beside
    the button, because the section that held it is not
    always on screen; inside the task's window when one is
    open, since the page behind it is covered."""

    if not st.session_state.git_message:
        return

    level, text = st.session_state.git_message

    st.session_state.git_message = None

    if level == "success":
        st.success(text)
    else:
        st.warning(text)
