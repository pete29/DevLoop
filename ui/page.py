"""The main column's own parts: what is selected, a task on its own, the task window."""

import os

import streamlit as st

from models.plan import Plan
from models.task_breakdown import TaskBreakdown
from ui import shared
from ui.actions import start_run
from ui.shared import plan_store, t
from ui.tasks import close_task, task_view


def status_line() -> None:
    """Where the selected task stands, and which repository is selected."""

    if st.session_state.task is None:
        st.info(t("requirement.status_new"))

    else:
        st.info(t("task.status_now", status=st.session_state.task.status.value))

    if st.session_state.repository_id:
        st.caption(
            t(
                "repo.current",
                name=shared.repositories_by_id[st.session_state.repository_id].name,
            )
        )

    else:
        st.warning(t("app.select_repository_first"))


def quick_task_panel() -> None:
    """A task described on its own, run as a plan of one task.

    It gets a branch before anything is generated, a
    background run, a pull request and a cost, like any
    planned task. Run in the page it blocked the tab and
    landed on whatever branch was checked out.
    """

    description = st.text_area(t("app.describe_task"))

    if not st.button(
        t("app.generate"),
        disabled=not st.session_state.repository_id,
    ) or not description:
        return

    target_path = shared.repositories_by_id[st.session_state.repository_id].path

    if not os.path.isdir(target_path):
        st.error(t("app.folder_missing", path=target_path))
        st.stop()

    lines = description.strip().splitlines()

    single = Plan(
        repository_id=st.session_state.repository_id,
        epic=description.strip(),
        tasks=[
            TaskBreakdown(
                id=1,
                title=lines[0].strip()[:120],
                description="\n".join(lines[1:]).strip(),
            )
        ],
    )

    plan_store.save(single)

    st.session_state.plan = single

    start_run(single, target_path, 1)


def task_window() -> None:
    """The selected task, in a large window over the page."""

    if not st.session_state.task:
        return

    lines = st.session_state.task.description.strip().splitlines()

    heading = lines[0][:80] if lines else t("task.details")

    st.dialog(heading, width="large", on_dismiss=close_task)(task_view)()
