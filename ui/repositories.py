"""Adding a repository, and creating a new one."""

import os
import streamlit as st
from services.repository_setup import check_new, create as create_repository, folder_name, pick_folder
from ui import shared
from ui.actions import register_repository
from ui.shared import repository_store, t


def name_from_path() -> None:
    """Fills the name from the folder, unless one was typed."""

    if not st.session_state.get("repo_add_name", "").strip():
        st.session_state.repo_add_name = folder_name(
            st.session_state.get("repo_add_path", "")
        )


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

        if not st.button(
            t("repo.add_button"),
            key="repo-add",
            use_container_width=True,
            type="primary",
        ):
            return

        path = os.path.normpath(new_path.strip()) if new_path.strip() else ""

        if not new_name.strip() or not path:
            st.error(t("repo.name_and_path_required"))

        elif not os.path.isdir(path):
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

        name = st.text_input(t("repo.new_name"), key="repo_new_name")

        if st.button(
            t("repo.pick"),
            key="repo-new-pick",
            use_container_width=True,
        ):

            chosen = pick_folder(st.session_state.repo_new_parent)

            if chosen:
                st.session_state.repo_new_parent = chosen

            st.rerun()

        parent = st.text_input(t("repo.new_parent"), key="repo_new_parent")

        description = st.text_input(
            t("repo.new_description"),
            key="repo_new_description",
        )

        on_github = st.checkbox(
            t("repo.new_on_github"),
            value=True,
            key="repo_new_on_github",
        )

        private = st.checkbox(
            t("repo.new_private"),
            value=True,
            key="repo_new_private",
            disabled=not on_github,
        )

        if on_github:
            st.caption(t("repo.new_token_note"))

        problem = check_new(parent.strip(), name.strip()) if name.strip() else ""

        if name.strip() and not problem:
            st.caption(
                t(
                    "repo.new_target",
                    path=os.path.join(parent.strip(), name.strip()),
                )
            )

        elif problem:
            st.caption(f"⚠️ {problem}")

        if not st.button(
            t("repo.new_create"),
            key="repo-new-create",
            use_container_width=True,
            type="primary",
            disabled=not name.strip() or bool(problem),
        ):
            return

        try:

            with st.spinner(t("repo.new_spinner")):

                made = create_repository(
                    parent.strip(),
                    name.strip(),
                    on_github,
                    private,
                    description,
                )

        except Exception as error:

            st.session_state.git_message = (
                "warning",
                t("repo.new_failed", reason=error),
            )

            st.rerun()

        register_repository(name.strip(), made.path)

        st.session_state.repo_new_reset = True

        st.session_state.git_message = (
            "success",
            t("repo.new_created", name=name.strip(), path=made.path)
            + (
                t("repo.new_created_github", url=made.html_url)
                if made.html_url
                else ""
            ),
        )

        st.rerun()
