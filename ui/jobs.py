"""Planning and revising in the background: starting it, and its panel.

Both used to run inside the page's script, which Streamlit
stops on any click: a requirement planned while someone
looked at the sidebar was thrown away unseen, and a revision
showed nothing of its progress. They now run in the worker,
like a plan's tasks, and this panel follows them.
"""

import streamlit as st

from services import plan_runner
from ui.actions import log_tail
from ui.shared import run_store, t


def start_job(kind: str, subject: str, repository_path: str, notes: str = "") -> None:
    """Hands planning or a revision to the worker, and watches it."""

    try:
        run = plan_runner.start(run_store, "", repository_path, kind=kind, subject=subject, notes=notes)

    except Exception as error:  # noqa: BLE001 -- shown, not raised
        st.session_state.git_message = ("warning", t("run.could_not_start", reason=error))

    else:
        st.session_state[f"watching-{kind}-{subject}"] = run.id

    st.rerun()


def job_active(kind: str, subject: str) -> bool:
    """Whether planning or a revision of this subject is under way."""

    run = run_store.latest_job(kind, subject)

    return run is not None and run.status.active


def job_panel(kind: str, subject: str, on_done) -> None:
    """The background job's progress; when it ends, on_done(run) once.

    Redrawn on its own every few seconds while it works; the
    whole page is redrawn when it ends, so what it made shows.
    """

    run = run_store.latest_job(kind, subject)

    if run is None:
        return

    key = f"watching-{kind}-{subject}"

    if run.status.active:

        st.session_state[key] = run.id

        st.fragment(run_every=3)(job_progress)(kind, subject)

        return

    if st.session_state.get(key) == run.id:

        st.session_state[key] = None

        on_done(run)

        st.session_state.git_message = (
            ("success" if run.status.value == "DONE" else "warning"),
            t("job.ended", status=run.status.value, message=run.message or ""),
        )

        st.rerun()

    if run.status.value != "DONE":
        st.caption(t("job.ended", status=run.status.value, message=run.message or ""))


def job_progress(kind: str, subject: str) -> None:
    """What the worker is doing now; the page catches up when it ends."""

    run = run_store.latest_job(kind, subject)

    if run is None or not run.status.active:
        st.rerun()

    st.info(t(f"job.{kind}", since=run.started_at[11:19]))

    console = log_tail(run, lines=8)

    if console:
        st.code(console, language="text")
