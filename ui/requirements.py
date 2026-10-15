"""The requirement view, and splitting a requirement into issues."""

import streamlit as st

from agents.issue_agent import IssueAgent, to_link
from agents.planner_agent import PlannerAgent
from agents.story_splitter import Story, StorySplitter, child_body, children_comment
from models.pull_request_info import PullRequestState
from models.requirement import RequirementSource, now
from services import plan_branch, usage_ledger
from ui.actions import continue_plan, plan_pull_request, plan_records, remote_of
from ui.shared import plan_store, repository_path_now, requirement_store, run_store, t


def requirement_view() -> None:
    """The selected requirement: its plans, its text, and what can be done with it."""

    if not st.session_state.requirement:
        return

    requirement = st.session_state.requirement

    requirement_header(requirement)

    requirement_plans(requirement)

    new_title = st.text_input(
        t("requirement.title"),
        value=requirement.title,
        key=f"title-{requirement.id}",
    )

    new_content = st.text_area(
        t("requirement.description"),
        value=requirement.content,
        height=220,
        key=f"content-{requirement.id}",
        help=t("requirement.description_help"),
    )

    requirement_buttons(requirement, new_title, new_content)

    github_buttons(requirement, new_title, new_content)

    st.divider()


def requirement_header(requirement) -> None:
    """Which requirement, and the issue it came from."""

    st.subheader(t("requirement.one"))

    if requirement.issue.exists:

        st.caption(
            t(
                "requirement.imported_from",
                label=requirement.issue.label,
            )
        )


def requirement_plans(requirement) -> None:
    """The requirement's status, and its plans with their progress."""

    plans_for = [
        item
        for item in plan_store.get_all()
        if item.requirement_id == requirement.id
    ]

    st.caption(
        t(
            "requirement.status",
            state=requirement.lifecycle(
                plans=len(plans_for),
                started=sum(
                    1
                    for item in plans_for
                    if item.started
                ),
                outstanding=sum(
                    len(item.remaining)
                    for item in plans_for
                ),
                delivered=sum(
                    1
                    for item in plans_for
                    if (
                        holder := plan_pull_request(
                            plan_records(item)
                        )
                    )
                    is not None
                    and holder.pull_request.state
                    == PullRequestState.MERGED
                ),
            ).value,
            when=requirement.updated_at[:19],
        )
    )

    # A requirement and its plans are one piece of work,
    # and the link was only ever stored, never shown: the
    # requirement said PLANNED and gave no way to reach
    # the plan that made it so.
    if plans_for:

        with st.expander(
            t(
                "requirement.linked_plans",
                count=len(plans_for),
            ),
            expanded=True,
        ):

            for linked in plans_for:

                counts = linked.dashboard()

                st.caption(
                    t(
                        "requirement.plan_progress",
                        done=counts["COMPLETED"],
                        total=counts["TOTAL"],
                        state=(
                            t("board.failed")
                            if counts["FAILED"]
                            else t("board.running")
                            if counts["RUNNING"]
                            else t("board.completed")
                            if not linked.remaining
                            else t("board.ready")
                        ),
                    )
                )

                st.progress(linked.percent_complete)

                if st.button(
                    t("requirement.open_plan"),
                    key=f"open-plan-{linked.id}",
                    use_container_width=True,
                ):
                    st.session_state.plan = linked

                    st.rerun()

                if st.button(
                    t("plan.continue"),
                    key=f"continue-plan-{linked.id}",
                    help=t("plan.continue_help"),
                    use_container_width=True,
                    disabled=not st.session_state.repository_id
                    or (
                        run_store.latest(linked.id) is not None
                        and run_store.latest(linked.id).status.active
                    ),
                ):
                    continue_plan(linked)

        # One branch per issue: a new plan joins the old
        # one's branch and pull request, which is worth
        # knowing before paying for it.
        next_branch = plan_branch.name(
            "", requirement.epic, requirement.issue.number
        )

        if requirement.issue.exists and any(
            plan_branch.of(item) == next_branch for item in plans_for
        ):
            st.caption(
                t("requirement.replan_note", branch=next_branch)
            )

    else:

        st.info(t("requirement.no_plans"))


def requirement_buttons(requirement, new_title, new_content) -> None:
    """Save, plan, delete."""

    save_col, plan_col, delete_col = st.columns(3)

    with save_col:

        save_requirement(requirement, new_title, new_content)

    with plan_col:

        generate_plan(requirement, new_title, new_content)

    with delete_col:

        delete_requirement(requirement)


def save_requirement(requirement, new_title, new_content) -> None:
    """Save the text as edited."""

    if st.button(t("requirement.save"), use_container_width=True):

        requirement.title = new_title

        requirement.content = new_content

        requirement.updated_at = now()

        requirement_store.save(requirement)

        st.session_state.requirement = requirement

        st.rerun()


def generate_plan(requirement, new_title, new_content) -> None:
    """Have the planner turn the requirement into a plan."""

    if st.button(
        t("requirement.generate_plan"),
        use_container_width=True,
        disabled=not st.session_state.repository_id
        or not new_content.strip(),
    ):

        requirement.title = new_title

        requirement.content = new_content

        requirement.updated_at = now()

        requirement_store.save(requirement)

        with st.spinner(t("plan.planner_spinner")):

            spent = usage_ledger.mark()

            try:

                plan = PlannerAgent().execute(
                    requirement.epic,
                    st.session_state.repository_id,
                    repository_path_now(),
                )

            except Exception as error:

                st.error(
                    t(
                        "plan.planner_failed",
                        reason=error,
                    )
                )

                st.stop()

            # Shown once, under the plan it paid for. Not
            # stored: the plan is the same plan whatever
            # it cost, and the tasks keep their own.
            st.session_state.plan_usage = (
                plan.id,
                usage_ledger.describe(
                    usage_ledger.since(spent)
                ),
            )

            plan.requirement_id = requirement.id

            plan.issue = requirement.issue

            plan.planning_cost = usage_ledger.dollars(
                usage_ledger.since(spent)
            )

            plan_store.save(plan)

            st.session_state.plan = plan

            st.rerun()


def delete_requirement(requirement) -> None:
    """Delete the requirement."""

    if st.button(
        t("requirement.delete"),
        use_container_width=True,
    ):

        requirement_store.delete(requirement.id)

        st.session_state.requirement = None

        st.rerun()


def github_buttons(requirement, new_title, new_content) -> None:
    """What the requirement can become on GitHub: an issue, or several."""

    requirement_remote = remote_of(requirement.repository_id)

    issue_col, split_col = st.columns(2)

    with issue_col:

        create_issue_button(requirement, new_title, new_content, requirement_remote)

    with split_col:

        split_button(requirement, new_title, new_content, requirement_remote)

    if not requirement_remote:
        st.caption(t("requirement.needs_remote"))

    split_panel(requirement, requirement_remote)


def create_issue_button(requirement, new_title, new_content, requirement_remote) -> None:
    """File a requirement written here as a GitHub issue."""

    # Only for a requirement written here: an imported
    # one already is an issue.
    if not requirement.issue.exists and st.button(
        t("requirement.create_issue"),
        use_container_width=True,
        disabled=not requirement_remote
        or not new_title.strip(),
    ):

        requirement.title = new_title

        requirement.content = new_content

        try:

            issue = IssueAgent.create(
                requirement_remote,
                new_title,
                new_content,
            )

        except Exception as error:

            st.session_state.git_message = (
                "warning",
                t("requirement.issue_failed", reason=error),
            )

        else:

            requirement.issue = to_link(issue)

            requirement.source = RequirementSource.GITHUB_ISSUE

            requirement.updated_at = now()

            requirement_store.save(requirement)

            st.session_state.requirement = requirement

            st.session_state.issues_from = None

            st.session_state.git_message = (
                "success",
                t(
                    "requirement.issue_created",
                    label=requirement.issue.label,
                ),
            )

        st.rerun()


def split_button(requirement, new_title, new_content, requirement_remote) -> None:
    """Ask the planner how to split the requirement into issues."""

    if st.button(
        t("split.button"),
        use_container_width=True,
        disabled=not requirement_remote
        or not new_content.strip(),
    ):

        with st.spinner(t("split.spinner")):

            try:

                stories = StorySplitter().execute(
                    f"{new_title}\n\n{new_content}"
                )

            except Exception as error:

                st.session_state.git_message = (
                    "warning",
                    t("split.failed", reason=error),
                )

            else:

                st.session_state.split = (requirement.id, stories)

        st.rerun()


def split_panel(requirement, remote_url: str) -> None:
    """The planner's proposed split, for a human to edit.

    Nothing is filed until the button: the model only
    proposes, and a wrong issue on someone's board is
    worse than none.
    """

    proposal = st.session_state.get("split")

    if not proposal or proposal[0] != requirement.id:
        return

    stories: list[Story] = proposal[1]

    st.markdown(f"**{t('split.heading')}**")

    st.caption(t("split.caption"))

    chosen: list[Story] = []

    for index, story in enumerate(stories):

        with st.container(border=True):

            keep = st.checkbox(
                t("split.include"),
                value=True,
                key=f"split-keep-{requirement.id}-{index}",
            )

            title = st.text_input(
                t("split.title"),
                value=story.title,
                key=f"split-title-{requirement.id}-{index}",
            )

            body = st.text_area(
                t("split.body"),
                value=story.body,
                height=160,
                key=f"split-body-{requirement.id}-{index}",
            )

            if keep and title.strip():
                chosen.append(Story(title=title, body=body))

    create_col, cancel_col = st.columns(2)

    with cancel_col:

        if st.button(
            t("split.cancel"),
            key=f"split-cancel-{requirement.id}",
            use_container_width=True,
        ):
            st.session_state.split = None

            st.rerun()

    with create_col:

        if not st.button(
            t("split.create", count=len(chosen)),
            key=f"split-create-{requirement.id}",
            disabled=not chosen or not remote_url,
            use_container_width=True,
            type="primary",
        ):
            return

    parent = requirement.issue.number

    created: list[tuple[int, str]] = []

    child_ids: list[int] = []

    linked = ""

    try:

        for story in chosen:

            issue = IssueAgent.create(
                remote_url,
                story.title,
                child_body(story, parent),
            )

            requirement_store.save(
                IssueAgent.to_requirement(
                    issue,
                    requirement.repository_id,
                )
            )

            created.append((issue.number, issue.title))

            child_ids.append(issue.id)

        # The parent keeps track of its children on GitHub,
        # where people look, rather than in a table here:
        # as real sub-issues, and as a comment only where
        # those are not available.
        linked = ""

        if parent > 0 and created:

            service = IssueAgent.service(remote_url)

            try:

                for child_id in child_ids:
                    service.add_sub_issue(parent, child_id)

                linked = t("split.linked", parent=parent)

            except Exception as error:

                service.add_comment(
                    parent,
                    children_comment(created),
                )

                linked = t(
                    "split.not_linked",
                    parent=parent,
                    reason=error,
                )

    except Exception as error:

        st.session_state.git_message = (
            "warning",
            t("split.partial", count=len(created), reason=error),
        )

    else:

        st.session_state.git_message = (
            "success",
            t(
                "split.created",
                count=len(created),
                labels=", ".join(f"#{number}" for number, _ in created),
            )
            + linked,
        )

    st.session_state.split = None

    # The sidebar's issue list was read before these existed.
    st.session_state.issues_from = None

    st.rerun()
