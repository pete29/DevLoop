"""DevLoop: the Streamlit page. The parts live in ui/."""

import os
import streamlit as st
from config.settings import Settings
from dotenv import load_dotenv
from models.plan import Plan
from models.task_breakdown import TaskBreakdown
from services import plan_runner
from services.translations import DEFAULT_LANGUAGE
from ui import shared
from ui.actions import start_run
from ui.plans import plan_view
from ui.requirements import requirement_view
from ui.shared import plan_store, run_store, show_message, t
from ui.sidebar import sidebar
from ui.tasks import close_task, task_view

load_dotenv()

shared.refresh()

# A worker that died says nothing; its process being gone
# is the only evidence, so every page load looks.
plan_runner.detect_interrupted(run_store)

if "task" not in st.session_state:
    st.session_state.task = None

if "repository_id" not in st.session_state:
    st.session_state.repository_id = None

# The outcome of the last git run, kept across the rerun
# that follows approval so the user actually sees it.
if "git_message" not in st.session_state:
    st.session_state.git_message = None

if "plan" not in st.session_state:
    st.session_state.plan = None

# The background run this page last saw active, so it can
# tell when that run ends and redraw once.
if "watching_run" not in st.session_state:
    st.session_state.watching_run = None

if "requirement" not in st.session_state:
    st.session_state.requirement = None

if "issues" not in st.session_state:
    st.session_state.issues = None

# Which remote the issues in session state came from.
# Streamlit reruns the whole script on every interaction,
# so without this the app would call GitHub on every
# click; with it, once per remote per session.
if "issues_from" not in st.session_state:
    st.session_state.issues_from = None

if "install_output" not in st.session_state:
    st.session_state.install_output = ""

if "language" not in st.session_state:
    st.session_state.language = DEFAULT_LANGUAGE

st.title(Settings.PAGE_TITLE)

if st.session_state.task is None:
    show_message()

sidebar()

if st.session_state.task is None:

    st.info(t("requirement.status_new"))

else:

    st.info(
        t(
            "task.status_now",
            status=st.session_state.task.status.value,
        )
    )

if st.session_state.repository_id:

    st.caption(
        t(
            "repo.current",
            name=shared.repositories_by_id[
                st.session_state.repository_id
            ].name,
        )
    )

else:

    st.warning(
        t("app.select_repository_first")
    )

requirement_view()

plan_view()

task_description = st.text_area(t("app.describe_task"))

if st.button(
    t("app.generate"),
    disabled=not st.session_state.repository_id,
) and task_description:

    target_path = shared.repositories_by_id[
        st.session_state.repository_id
    ].path

    if not os.path.isdir(target_path):

        st.error(
            t("app.folder_missing", path=target_path)
        )

        st.stop()

    # A task on its own is a plan of one task: it gets a
    # branch before anything is generated, a background run,
    # a pull request and a cost, like any planned task. Run
    # in the page it blocked the tab and landed on whatever
    # branch was checked out.
    lines = task_description.strip().splitlines()

    single = Plan(
        repository_id=st.session_state.repository_id,
        epic=task_description.strip(),
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

if st.session_state.task:

    lines = st.session_state.task.description.strip().splitlines()

    heading = lines[0][:80] if lines else t("task.details")

    st.dialog(
        heading,
        width="large",
        on_dismiss=close_task,
    )(task_view)()
