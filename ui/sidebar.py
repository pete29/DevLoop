"""The sidebar."""

import os
import streamlit as st
from agents.issue_agent import IssueAgent
from config.settings import Settings
from database.repository_repository import same_path
from models.repository_context import TestFramework
from models.requirement import Requirement, now
from services import costs
from services.git_service import GitError, GitService
from services.github_issue_service import tree as issue_tree
from services.repository_context import describe
from services.translations import LANGUAGES
from ui import shared
from ui.plans import install_panel
from ui.repositories import add_repository_panel, new_repository_panel
from ui.shared import plan_store, repository, repository_store, requirement_store, t


def sidebar() -> None:
    """The sidebar: language, cost, repositories, requirements, issues, plans, history."""

    with st.sidebar:

        st.session_state.language = st.selectbox(
            t("app.language"),
            tuple(LANGUAGES),
            format_func=lambda code: LANGUAGES[code],
            index=tuple(LANGUAGES).index(
                st.session_state.language
            ),
        )

        # Every task and plan of the month, whichever repository.
        st.caption(
            t(
                "cost.month",
                spent=f"{costs.month_spent(repository.get_all(), plan_store.get_all(), now()[:7]):.2f}",
            )
        )

        if st.button(t("cost.history"), key="cost-history", use_container_width=True):
            st.session_state.show_costs = True
            st.rerun()

        st.divider()

        st.header(t("repo.heading"))

        if shared.repositories:

            if st.session_state.repository_id not in shared.repositories_by_id:
                st.session_state.repository_id = shared.repositories[0].id

            st.session_state.repository_id = st.selectbox(
                t("repo.active"),
                [item.id for item in shared.repositories],
                format_func=lambda item_id: (
                    shared.repositories_by_id[item_id].name
                ),
                index=[item.id for item in shared.repositories].index(
                    st.session_state.repository_id
                ),
            )

            active_repository = shared.repositories_by_id[st.session_state.repository_id]

            st.caption(active_repository.path)

            if not os.path.isdir(active_repository.path):

                st.warning(
                    t("repo.path_missing")
                )

            else:

                # Read from disk every time it is drawn. A
                # stored context would be wrong the moment a
                # task writes a file.
                context = describe(active_repository.path)

                with st.expander(
                    t(
                        "repo.context_heading",
                        state=context.state.value,
                    ),
                    expanded=context.bootstrap_needed,
                ):

                    left, right = st.columns(2)

                    with left:
                        st.metric(
                            t("context.typescript"),
                            "yes" if context.typescript else "no",
                        )
                        st.metric(
                            t("context.tests_runnable"),
                            "yes" if context.tests_runnable else "no",
                        )

                    with right:
                        st.metric(
                            t("context.package_json"),
                            "yes" if context.package_json else "no",
                        )
                        st.metric(
                            t("context.git"),
                            "yes" if context.git else "no",
                        )

                    framework = (
                        context.test_framework.value.title()
                        if context.test_framework
                        != TestFramework.NONE
                        else t("context.framework_none")
                    )

                    st.caption(
                        t(
                            "context.summary_line",
                            files=context.file_count,
                            framework=framework,
                            folders=(
                                t(
                                    "context.folders_suffix",
                                    names=", ".join(
                                        context.source_folders
                                    ),
                                )
                                if context.source_folders
                                else ""
                            ),
                        )
                    )

                    if context.missing:

                        st.info(
                            t(
                                "plan.scaffolding_created"
                                if Settings.AUTO_BOOTSTRAP
                                else "context.scaffolding_off",
                                names=", ".join(context.missing),
                            )
                        )

                    if (
                        context.test_framework
                        == TestFramework.VITEST
                        and not context.dependencies_installed
                    ):

                        st.warning(
                            t("context.vitest_not_installed")
                        )

                        install_panel(
                            active_repository.path,
                            "sidebar",
                        )

                    elif context.test_framework not in (
                        TestFramework.NONE,
                        TestFramework.VITEST,
                    ):

                        st.warning(
                            t(
                                "context.other_framework",
                                framework=(
                                    context.test_framework.value.title()
                                ),
                            )
                        )

            linked_tasks = sum(
                1
                for item in repository.get_all()
                if item.repository_id == active_repository.id
                or same_path(
                    item.repository_path,
                    active_repository.path,
                )
            )

            confirmed = True

            if linked_tasks:

                confirmed = st.checkbox(
                    t(
                        "repo.remove_anyway",
                        count=linked_tasks,
                    ),
                )

            if st.button(
                t("repo.remove"),
                use_container_width=True,
                disabled=not confirmed,
            ):

                repository_store.delete(active_repository.id)

                st.session_state.repository_id = None

                st.rerun()

        else:

            st.info(t("repo.none_yet"))

        add_repository_panel()

        new_repository_panel()

        st.divider()

        st.header(t("requirement.heading"))

        requirements = requirement_store.get_all()

        if not requirements:
            st.write(t("requirement.none_yet"))

        for item in requirements:

            if st.button(
                item.label[:34],
                key=f"req-{item.id}",
                use_container_width=True,
            ):
                st.session_state.requirement = (
                    requirement_store.get_by_id(item.id)
                )

                st.session_state.plan = None

                st.rerun()

        if st.button(
            t("requirement.new"),
            use_container_width=True,
        ):
            st.session_state.requirement = Requirement(
                repository_id=st.session_state.repository_id
                or "",
            )

            st.session_state.plan = None

            st.rerun()

        st.divider()

        st.header(t("issue.heading"))

        active = (
            shared.repositories_by_id.get(
                st.session_state.repository_id
            )
            if st.session_state.repository_id
            else None
        )

        remote_url = ""

        if active and GitService(active.path).is_repository():

            try:
                remote_url = GitService(active.path).remote_url()

            except GitError:
                remote_url = ""

        # Fetched when the app opens rather than waiting for a
        # button: the backlog is where work starts, and a
        # button that has to be pressed before anything is
        # visible is a button that gets forgotten.
        stale = (
            remote_url
            and st.session_state.issues_from != remote_url
        )

        # Evaluated before the `or`, not inside it: a
        # short-circuit would skip the call that draws the
        # button, and a stale read would make it vanish.
        pressed = st.button(
            t("issue.load"),
            use_container_width=True,
            disabled=not remote_url,
        )

        if stale or pressed:
            found, problem = IssueAgent.open_issues(remote_url)

            st.session_state.issues = found

            # Recorded even when the read failed, so a remote
            # with no token is tried once rather than on every
            # rerun.
            st.session_state.issues_from = remote_url

            if problem and not stale:

                # On an automatic read the reason belongs under
                # the list, not as a banner over the whole app.
                st.session_state.git_message = (
                    "warning",
                    t("issue.could_not_read", reason=problem),
                )

            st.session_state.issues_problem = problem

            if not stale:
                st.rerun()

        if st.session_state.get("issues_problem"):
            st.caption(
                t(
                    "issue.could_not_read",
                    reason=st.session_state.issues_problem,
                )
            )

        if not remote_url:
            st.caption(
                t("issue.needs_github_remote")
            )

        # Sub-issues under their parent, so a split reads as
        # the one piece of work it is.
        for issue, depth in issue_tree(st.session_state.issues or []):

            progress = f" · {issue.progress}" if issue.progress else ""

            if depth:

                _, holder = st.columns([depth, 10])

            else:

                holder = st.container()

            with holder:

                pressed = st.button(
                    ("↳ " if depth else "") + issue.label[: 34 - 4 * depth] + progress,
                    key=f"issue-{issue.number}",
                    use_container_width=True,
                    help=issue.label,
                )

            if pressed:
                existing = requirement_store.get_by_issue(
                    issue.number
                )

                imported = IssueAgent.to_requirement(
                    issue,
                    st.session_state.repository_id or "",
                    existing,
                )

                requirement_store.save(imported)

                st.session_state.requirement = imported

                st.session_state.plan = None

                st.rerun()

        st.divider()

        st.header(t("plan.heading"))

        plans = plan_store.get_all()

        if not plans:
            st.write(t("plan.none_yet"))

        for plan_item in plans:

            label = (
                f"{len(plan_item.completed)}/"
                f"{len(plan_item.tasks)} | "
                f"{plan_item.epic[:28]}"
            )

            if st.button(
                label,
                key=f"plan-{plan_item.id}",
                use_container_width=True,
            ):
                st.session_state.plan = plan_store.get_by_id(
                    plan_item.id
                )

                st.rerun()

        st.divider()

        st.header(t("task.history"))

        tasks = repository.get_all()

        if not tasks:
            st.write(t("task.none_yet"))

        for task_item in tasks:

            label = f"{task_item.status.value} | " f"{task_item.description[:30]}"

            if st.button(
                label,
                key=task_item.id,
                use_container_width=True,
            ):
                st.session_state.task = repository.get_by_id(task_item.id)

                st.rerun()
