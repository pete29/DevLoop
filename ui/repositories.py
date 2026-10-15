"""Adding a repository, and creating a new one."""

import os

import streamlit as st

from services.git_service import GitError
from services.repository_setup import check_existing, check_new, create as create_repository, folder_name, pick_folder, start_git
from ui import shared
from ui.actions import register_repository
from ui.shared import repository_store, t


def add_repository_panel() -> None:
    """Registers a folder that already exists.

    Picked with the system's folder window, or typed; the
    name is the folder's unless changed. Typing a path and
    a name nobody needed to think about was the old form.
    """

    # Cleared here, before the inputs exist: Streamlit
    # refuses a change to a widget's value after it is drawn.
    if st.session_state.pop("repo_add_reset", False):
        st.session_state.repo_add_name = ""
        st.session_state.repo_add_path = ""

    # The same for a path chosen by a button below the field.
    chosen_root = st.session_state.pop("repo_add_root", "")

    if chosen_root:
        st.session_state.repo_add_path = chosen_root
        st.session_state.repo_add_name = folder_name(chosen_root)

    with st.expander(t("repo.add")):

        if st.button(
            t("repo.pick"),
            key="repo-add-pick",
            use_container_width=True,
        ):

            chosen = pick_folder(st.session_state.get("repo_add_path", ""))

            if chosen:
                st.session_state.repo_add_path = chosen
                st.session_state.repo_add_name = folder_name(chosen)

            else:
                st.session_state.git_message = ("warning", t("repo.pick_none"))

            st.rerun()

        new_path = st.text_input(
            t("repo.path"),
            key="repo_add_path",
            on_change=name_from_path,
        )

        new_name = st.text_input(t("repo.name"), key="repo_add_name")

        path = os.path.normpath(new_path.strip()) if new_path.strip() else ""

        problem = folder_problem(path)

        if not st.button(
            t("repo.add_button"),
            key="repo-add",
            use_container_width=True,
            type="primary",
            disabled=problem in ("not_git", "inside"),
        ):
            return

        if not new_name.strip() or not path:
            st.error(t("repo.name_and_path_required"))

        elif problem == "missing":
            st.error(t("repo.folder_missing", path=path))

        elif repository_store.get_by_path(path):
            st.error(t("repo.already_registered"))

        else:
            register_repository(new_name.strip(), path)

            st.session_state.repo_add_reset = True

            st.session_state.git_message = (
                "success",
                t("repo.added", name=new_name.strip()),
            )

            st.rerun()


def folder_problem(path: str) -> str:
    """Says what is wrong with the folder, and offers the fix.

    A folder without git was accepted before, and every
    plan in it failed at its first step, the branch.
    """

    if not path:
        return "missing"

    problem, root = check_existing(path)

    if problem == "not_git":

        st.warning(t("repo.not_git"))

        if st.button(t("repo.start_git"), key="repo-add-git-init", use_container_width=True):

            try:
                start_git(path)

                st.session_state.git_message = ("success", t("repo.git_started", path=path))

            except (GitError, OSError) as error:
                st.session_state.git_message = ("warning", t("repo.git_start_failed", reason=error))

            st.rerun()

    elif problem == "inside":

        st.warning(t("repo.inside", root=root))

        if st.button(t("repo.use_root", root=root), key="repo-add-use-root", use_container_width=True):

            st.session_state.repo_add_root = root

            st.rerun()

    return problem


def name_from_path() -> None:
    """Fills the name from the folder, unless one was typed."""

    if not st.session_state.get("repo_add_name", "").strip():
        st.session_state.repo_add_name = folder_name(
            st.session_state.get("repo_add_path", "")
        )


def new_repository_panel() -> None:
    """A repository that does not exist yet, made here.

    A folder with git, and -- by default -- a private
    repository on GitHub set as its origin, so it is ready
    for plans, pull requests and issues at once.
    """

    if st.session_state.pop("repo_new_reset", False):
        st.session_state.repo_new_name = ""
        st.session_state.repo_new_description = ""

    # Next to the repositories already registered, unless a
    # parent was chosen before.
    if "repo_new_parent" not in st.session_state:
        st.session_state.repo_new_parent = (
            os.path.dirname(shared.repositories[0].path)
            if shared.repositories
            else os.path.expanduser("~")
        )

    with st.expander(t("repo.new")):

        name, parent, description, on_github, private = new_repository_fields()

        problem = check_new(parent, name) if name else ""

        if name and not problem:
            st.caption(t("repo.new_target", path=os.path.join(parent, name)))

        elif problem:
            st.caption(f"⚠️ {problem}")

        if st.button(
            t("repo.new_create"),
            key="repo-new-create",
            use_container_width=True,
            type="primary",
            disabled=not name or bool(problem),
        ):
            make_repository(name, parent, description, on_github, private)


def new_repository_fields() -> tuple[str, str, str, bool, bool]:
    """Name, parent folder, description, and where it lives."""

    name = st.text_input(t("repo.new_name"), key="repo_new_name")

    if st.button(t("repo.pick"), key="repo-new-pick", use_container_width=True):

        chosen = pick_folder(st.session_state.repo_new_parent)

        if chosen:
            st.session_state.repo_new_parent = chosen

        st.rerun()

    parent = st.text_input(t("repo.new_parent"), key="repo_new_parent")

    description = st.text_input(t("repo.new_description"), key="repo_new_description")

    on_github = st.checkbox(t("repo.new_on_github"), value=True, key="repo_new_on_github")

    private = st.checkbox(
        t("repo.new_private"),
        value=True,
        key="repo_new_private",
        disabled=not on_github,
    )

    if on_github:
        st.caption(t("repo.new_token_note"))

    return name.strip(), parent.strip(), description, on_github, private


def make_repository(name: str, parent: str, description: str, on_github: bool, private: bool) -> None:
    """Creates it, registers it, and says where it is."""

    try:

        with st.spinner(t("repo.new_spinner")):
            made = create_repository(parent, name, on_github, private, description)

    except Exception as error:

        st.session_state.git_message = ("warning", t("repo.new_failed", reason=error))

        st.rerun()

    register_repository(name, made.path)

    st.session_state.repo_new_reset = True

    st.session_state.git_message = (
        "success",
        t("repo.new_created", name=name, path=made.path)
        + (t("repo.new_created_github", url=made.html_url) if made.html_url else ""),
    )

    st.rerun()
