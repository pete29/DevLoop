"""The task window: what a task produced, and the three answers to it."""

import streamlit as st

from agents.git_agent import GitAgent
from agents.issue_agent import IssueAgent
from agents.pull_request_agent import PullRequestAgent
from models.compile_result import CompileStatus
from models.file_type import FileType
from models.git_push_operation import PushStatus
from models.pull_request_info import PullRequestState
from models.task import Task
from models.task_status import TaskStatus
from models.test_result import TestStatus
from services.git_diff_service import GitDiffService
from services.git_service import GitError, GitService
from services.task_rollback import roll_back
from ui.actions import accept_record, install_and_recheck, plan_context, reopen_in_plan, revise_task
from ui import shared
from ui.shared import file_content, repository, repository_label, resolve_repository, show_files, show_message, t


def close_task() -> None:

    st.session_state.task = None


def task_view() -> None:
    """One task, in a window over the page.

    Drawn inline it made the page several screens long
    below the plan. Every action inside reruns the app,
    and the window opens again while the task is selected;
    closing it deselects the task.
    """

    task: Task = st.session_state.task

    show_message()

    task_summary(task)

    task_repository = resolve_repository(task)

    task_root = (
        task_repository.path
        if task_repository is not None
        else task.repository_path
    )

    task_steps(task)

    task_metrics(task)

    task_alerts(task)

    task_tabs(task, task_repository, task_root)

    git_section(task)

    st.divider()

    packages_panel(task)

    revision_panel(task)

    decision_buttons(task)


def task_summary(task) -> None:
    """When it was made, where it stands, which repository and issue."""

    st.write(t("task.created", when=task.created_at))

    st.write(
        t("task.status_line", status=task.status.value)
    )

    st.write(
        t(
            "task.repository_line",
            name=repository_label(task),
        )
    )

    if task.issue.exists:

        st.write(
            f"**Issue:** [{task.issue.label}]"
            f"({task.issue.url})"
            if task.issue.url
            else f"**Issue:** {task.issue.label}"
        )


def task_steps(task) -> None:
    """What was asked, and every step the run took, in order."""

    st.write(
        t("task.description_line", text=task.description)
    )

    with st.expander(
        t("steps.heading", count=len(task.steps)),
    ):

        if not task.steps:

            st.caption(t("steps.none"))

        for step in task.steps:

            st.write(
                "{mark} `{at}` **{name}** {detail}{took}".format(
                    mark="✅" if step.ok else "⚠️",
                    at=step.at[11:19],
                    name=t(step.name),
                    detail=step.detail,
                    took=(
                        f" · {step.duration}"
                        if step.duration
                        else ""
                    ),
                )
            )


def task_metrics(task) -> None:
    """The review's numbers at a glance."""

    metric_1, metric_2, metric_3 = st.columns(3)

    with metric_1:

        st.metric(
            t("task.score"),
            f"{task.architecture_score}/100",
        )

    with metric_2:

        st.metric(
            t("task.recommendation"),
            task.recommendation.value,
        )

    with metric_3:

        st.metric(
            t("task.review_iterations"),
            task.review_iterations,
        )

    (
        metric_4,
        metric_5,
        metric_6,
    ) = st.columns(3)

    with metric_4:

        st.metric(
            t("review.blockers"),
            len(task.blockers),
        )

    with metric_5:

        st.metric(
            t("review.warnings"),
            len(task.warnings),
        )

    with metric_6:

        st.metric(
            t("review.suggestions"),
            len(task.suggestions),
        )


def task_alerts(task) -> None:
    """What stands between this code and approval, before the details."""

    compiled = task.compile_result

    if compiled.status == CompileStatus.FAILED:

        st.error(
            t("types.failed", summary=compiled.summary)
        )

        with st.expander(
            t("types.errors", count=len(compiled.errors)),
            expanded=True,
        ):

            for problem in compiled.errors[:30]:
                st.write(f"- `{problem}`")

    elif compiled.status == CompileStatus.UNAVAILABLE:

        st.warning(
            t("types.unavailable", reason=compiled.reason)
        )

    elif compiled.status == CompileStatus.PASSED:

        st.success(t("types.passed"))

    if (
        compiled.blocks_delivery
        and task.test_result.status == TestStatus.NOT_RUN
    ):

        st.warning(t("tests.skipped_no_compile"))

    elif task.test_result.status == TestStatus.FAILED:

        st.error(
            t(
                "tests.failed_summary",
                summary=task.test_result.summary,
            )
        )

    elif task.test_result.status == TestStatus.ERROR:

        st.error(
            t("tests.incomplete")
        )

    elif task.test_result.status == TestStatus.PASSED:

        st.success(
            t(
                "tests.passed_summary",
                summary=task.test_result.summary,
            )
        )

    elif task.test_result.status == TestStatus.UNAVAILABLE:

        st.warning(
            t("tests.not_run_warning")
        )

    if task.structural:

        st.error(
            t(
                "structural.count_see_review",
                count=len(task.structural),
            )
        )

    if task.architecture_score > 0:

        st.progress(task.architecture_score / 100)


def task_tabs(task, task_repository, task_root) -> None:
    """The run's results, one tab per kind."""

    (
        tab_code,
        tab_review,
        tab_structure,
        tab_history,
        tab_tests,
        tab_files,
        tab_diff,
    ) = st.tabs(
        [
            t("tab.code"),
            t("tab.review"),
            t("tab.structural"),
            t("tab.history"),
            t("tab.tests"),
            t("tab.files"),
            t("tab.diff"),
        ]
    )

    with tab_code:

        code_tab(task, task_root)

    with tab_review:

        review_tab(task)

    with tab_structure:

        structure_tab(task)

    with tab_history:

        history_tab(task)

    with tab_tests:

        tests_tab(task, task_root)

    with tab_files:

        files_tab(task, task_repository, task_root)

    with tab_diff:

        diff_tab(task, task_root)


def code_tab(task, task_root) -> None:
    """The source files, read from disk."""

    if task.generated_files:

        show_files(
            task_root,
            [
                item
                for item in task.generated_files
                if item.file_type == FileType.SOURCE
            ],
            t("files.no_source"),
        )

    elif task.generated_code:

        st.code(
            task.generated_code,
            language="typescript",
        )

    else:

        st.warning(t("files.no_code"))


def review_tab(task) -> None:
    """The Architect's design findings."""

    st.caption(
        t("review.scope")
    )

    if task.architecture_review:

        st.markdown(task.architecture_review)

    else:

        st.info(t("review.none"))


def structure_tab(task) -> None:
    """What the deterministic checks found."""

    st.caption(
        t("structural.source")
    )

    if task.structural:

        for finding in task.structural:
            st.error(finding)

    else:

        st.success(t("structural.none"))


def history_tab(task) -> None:
    """Every review round, and what each one resolved."""

    if task.review_history:

        for review in task.review_history:

            st.subheader(
                t(
                    "history.iteration",
                    n=review.iteration,
                )
            )

            st.write(
                t("history.score", score=review.score)
            )

            st.write(
                t(
                    "history.recommendation",
                    value=review.recommendation.value,
                )
            )

            (
                history_1,
                history_2,
                history_3,
            ) = st.columns(3)

            with history_1:

                st.metric(
                    t("review.blockers"),
                    len(review.blockers),
                )

            with history_2:

                st.metric(
                    t("review.warnings"),
                    len(review.warnings),
                )

            with history_3:

                st.metric(
                    t("review.suggestions"),
                    len(review.suggestions),
                )

            if review.structural:

                st.caption(
                    t(
                        "structural.count",
                        count=len(review.structural),
                    )
                )

            st.markdown(review.review)

            st.divider()

    else:

        st.info(t("review.no_history"))


def tests_tab(task, task_root) -> None:
    """The test run, then the generated suites."""

    st.subheader(t("tests.execution"))

    result = task.test_result

    if result.status == TestStatus.NOT_RUN:

        st.info(t("tests.never_run"))

    elif result.status == TestStatus.UNAVAILABLE:

        st.warning(result.output)

    else:

        if result.passed:
            st.success("PASS")
        else:
            st.error(result.status.value)

        (
            test_1,
            test_2,
            test_3,
            test_4,
        ) = st.columns(4)

        with test_1:
            st.metric(t("board.total"), result.total_tests)

        with test_2:
            st.metric(t("tests.passed"), result.passed_tests)

        with test_3:
            st.metric(t("tests.failed"), result.failed_tests)

        with test_4:
            st.metric(
                t("tests.duration"),
                f"{result.duration_seconds:.1f}s",
            )

        if result.executed_at:
            st.caption(
                t(
                    "tests.executed_at",
                    when=result.executed_at[:19],
                )
            )

        with st.expander(
            t("tests.output"),
            expanded=not result.passed,
        ):
            st.code(result.output, language="text")

    st.divider()

    if task.generated_files:

        show_files(
            task_root,
            [
                item
                for item in task.generated_files
                if item.file_type == FileType.TEST
            ],
            "No test files.",
        )

    elif task.generated_tests:

        st.code(
            task.generated_tests,
            language="typescript",
        )

    else:

        st.info(t("tests.none"))


def files_tab(task, task_repository, task_root) -> None:
    """Every file the run wrote, read back from disk."""

    root = task_root

    if task.environment:

        # A change this run made to the repository that
        # is not a generated file, so nothing else here
        # would mention it.
        st.info(
            t(
                "task.scaffolding",
                names=", ".join(task.environment),
            )
        )

    if not task.generated_files:

        st.info(t("files.none_written"))

    elif not root:

        st.warning(
            t("files.no_path")
        )

        for generated in task.generated_files:
            st.write(f"`{generated.path}`")

    else:

        st.caption(t("files.written_to", path=root))

        if task_repository is None:

            st.info(
                t("files.unregistered")
            )

        for generated in task.generated_files:

            content = file_content(root, generated)

            with st.expander(
                f"{generated.file_type.value} · "
                f"{generated.path}",
                expanded=True,
            ):

                if content is None:

                    st.warning(
                        t("files.gone")
                    )

                else:

                    st.code(
                        content,
                        language="typescript",
                    )


def diff_tab(task, task_root) -> None:
    """What these files would change in the repository."""

    st.caption(
        t("diff.scope")
    )

    if not task.generated_files:

        st.info(t("files.none_generated"))

    elif not task_root:

        st.warning(
            t("diff.no_repository")
        )

    else:

        live_diffs = GitDiffService.compare(
            task_root,
            [
                item.path
                for item in task.generated_files
            ],
        )

        # Once committed there is nothing left to
        # compare, so the stored verdicts are the
        # evidence of what was reviewed.
        shown = (
            task.diffs
            if task.git_operation.committed
            and task.diffs
            else live_diffs
        )

        counts = GitDiffService.summary(shown)

        (
            diff_1,
            diff_2,
            diff_3,
        ) = st.columns(3)

        with diff_1:
            st.metric(t("diff.added"), counts["added"])

        with diff_2:
            st.metric(t("diff.modified"), counts["modified"])

        with diff_3:
            st.metric(t("diff.deleted"), counts["deleted"])

        if counts["unchanged"]:

            st.caption(
                t(
                    "diff.already_matching",
                    count=counts["unchanged"],
                )
            )

        if task.git_operation.committed:

            st.info(
                t(
                    "diff.already_committed",
                    hash=task.git_operation.short_hash,
                )
            )

        st.divider()

        for diff in shown:

            with st.expander(
                f"{diff.change_type.value} · "
                f"{diff.file_path}",
                expanded=diff.is_change,
            ):

                if diff.diff_content:

                    st.code(
                        diff.diff_content,
                        language="diff",
                    )

                elif diff.change_type.value == "unchanged":

                    st.caption(
                        t("diff.identical")
                    )

                else:

                    st.caption(
                        t("diff.unavailable")
                    )


def git_section(task) -> None:
    """The task's way into git and onto GitHub."""

    st.divider()

    st.subheader(t("context.git"))

    if task.git_operation.committed:

        commit_details(task)

        remote_section(task)

    else:

        commit_preview(task)


def commit_details(task) -> None:
    """The commit an approved task became."""

    st.success(
        t(
            "git.committed_to",
            branch=task.git_operation.branch_name,
        )
    )

    git_1, git_2 = st.columns(2)

    with git_1:

        st.metric(
            t("git.branch"),
            task.git_operation.branch_name,
        )

    with git_2:

        st.metric(
            t("git.commit"),
            task.git_operation.short_hash,
        )

    st.caption(
        t(
            "git.created_at",
            when=task.git_operation.created_at[:10],
        )
    )

    with st.expander(t("git.commit_message")):

        st.code(
            task.git_operation.commit_message,
            language="text",
        )


def remote_section(task) -> None:
    """The remote side: push, then pull request."""

    st.divider()

    st.subheader(t("git.remote"))

    if task.git_push.pushed:

        push_details(task)

        pull_request_section(task)

    else:

        push_form(task)


def push_details(task) -> None:
    """Where the branch went, and what follows it."""

    st.success(
        t(
            "git.push_succeeded",
            where=task.git_push.remote_branch,
        )
    )

    push_1, push_2 = st.columns(2)

    with push_1:
        st.metric(t("git.remote"), task.git_push.remote_name)

    with push_2:
        st.metric(
            t("git.remote_branch"),
            task.git_push.branch_name,
        )

    if task.git_push.remote_url:
        st.caption(task.git_push.remote_url)

    if task.git_push.pushed_at:
        st.caption(
            t(
                "git.pushed",
                where=task.git_push.pushed_at[:19],
            )
        )

    st.divider()

    st.subheader(t("pr.heading"))


def pull_request_section(task) -> None:
    """The pull request, or the way to open one."""

    if task.pull_request.exists:

        pull_request_details(task)

    else:

        pull_request_form(task)


def pull_request_details(task) -> None:
    """The pull request that exists for this task's branch."""

    st.success(
        f"{task.pull_request.label} "
        f"{task.pull_request.state.value}"
    )

    pr_1, pr_2 = st.columns(2)

    with pr_1:
        st.metric(
            t("pr.state"),
            task.pull_request.state.value,
        )

    with pr_2:
        st.metric(
            t("git.branch"),
            task.pull_request.branch,
        )

    st.markdown(
        f"[{task.pull_request.url}]"
        f"({task.pull_request.url})"
    )

    if task.pull_request.created_at:
        st.caption(
            t(
                "git.created_at",
                when=task.pull_request.created_at[:19],
            )
        )


def pull_request_form(task) -> None:
    """Opening the pull request: what it would say, and the button."""

    if task.pull_request.state == PullRequestState.FAILED:
        st.error(t("pr.failed", reason=task.pull_request.error))

    pr_plan, pr_records = plan_context(task)

    pull_request_preview(PullRequestAgent.preview(task, pr_plan, pr_records))

    pr_allowed, pr_reason = PullRequestAgent.can_create(task)

    if not pr_allowed:
        st.warning(pr_reason)

    st.caption(t("pr.note"))

    if st.button(t("pr.create"), disabled=not pr_allowed):

        st.session_state.git_message = open_pull_request(task, pr_plan, pr_records)

        st.rerun()


def pull_request_preview(preview: dict) -> None:
    """Where the pull request would go, and what it would say."""

    if preview["owner"]:
        st.write(t("pr.repository_line", owner=preview["owner"], repo=preview["repository"]))

    st.write(t("git.branch_line", branch=preview["branch"]))

    st.write(t("pr.title_line", title=preview["title"]))

    with st.expander(t("pr.description_preview")):
        st.code(preview["body"], language="markdown")


def open_pull_request(task, plan, records) -> tuple[str, str]:
    """Opens it, tells the issue, and says how both went."""

    info = PullRequestAgent.execute(task, plan=plan, records=records)

    repository.update_pull_request(task.id, info)

    task.pull_request = info

    if not info.exists:
        return "warning", f"Pull request failed: {info.error}"

    if not task.issue.exists:
        return "success", f"Opened {info.label}: {info.url}"

    # Tell the backlog what happened. A failure here never
    # undoes the pull request it is reporting.
    reported, detail = IssueAgent.report(task, task.git_push.remote_url)

    if reported:
        return "success", f"Opened {info.label} and commented on {task.issue.label}"

    return "warning", f"Opened {info.label}, but the issue was not updated: {detail}"


def push_form(task) -> None:
    """Pushing the branch: what would be sent, and the button."""

    if task.git_push.status == PushStatus.FAILED:
        st.error(t("git.push_failed", reason=task.git_push.error))

    preview = GitAgent.push_preview(task)

    st.write(t("git.remote_line", remote=preview["remote"]))

    st.write(t("git.branch_line", branch=preview["branch"]))

    st.write(t("git.files_line", count=len(preview["files"])))

    if preview["remote_url"]:
        st.caption(preview["remote_url"])

    allowed, reason = GitAgent.can_push(task)

    if not allowed:
        st.warning(reason)

    st.caption(t("git.push_note"))

    if st.button(t("git.push"), disabled=not allowed):

        st.session_state.git_message = push_branch(task)

        st.rerun()


def push_branch(task) -> tuple[str, str]:
    """Pushes, refreshes the plan's pull request, and says how it went."""

    result = GitAgent.push(task)

    repository.update_git_push(task.id, result)

    task.git_push = result

    if not result.pushed:
        return "warning", f"Push failed: {result.error}"

    # A plan's PR describes every task on the branch; this
    # push added one, so the description is rebuilt.
    # Opening the PR is still a separate click.
    push_plan, push_records = plan_context(task)

    synced = (
        PullRequestAgent.sync(task, push_plan, push_records)
        if push_plan is not None
        else None
    )

    if synced is None:
        return "success", f"Pushed {result.remote_branch}"

    if not synced.exists:
        return "warning", t("pr.sync_failed", branch=result.remote_branch, reason=synced.error)

    repository.update_pull_request(task.id, synced)

    return "success", t("pr.synced", branch=result.remote_branch, label=synced.label)


def commit_preview(task) -> None:
    """What approving would commit, before it does."""

    preview = GitAgent.preview(task)

    st.write(
        t(
            "git.branch_line",
            branch=preview["branch"],
        )
    )

    if preview["files"]:

        for path in preview["files"]:
            st.write(f"+ `{path}`")

    else:

        st.info(t("git.nothing_to_commit"))

    if task.repository_path and not GitService(
        task.repository_path
    ).is_repository():

        st.warning(
            t(
                "git.not_a_repository",
                path=task.repository_path,
            )
        )

    if task.status != TaskStatus.APPROVED:

        st.caption(
            t("git.approve_note")
        )

    with st.expander(t("git.commit_message_preview")):

        st.code(preview["message"], language="text")


def packages_panel(task) -> None:
    """The packages a task's code needs, and the button."""

    if not task.packages or task.status != TaskStatus.WAITING_FOR_APPROVAL:
        return

    names = ", ".join(task.packages)

    st.warning(t("packages.needed", names=names))

    if not st.button(
        t("packages.install", names=names),
        key=f"packages-{task.id}",
        type="primary",
        use_container_width=True,
        disabled=shared.month_blocked,
    ):
        return

    try:

        with st.spinner(t("packages.spinner")):
            checked = install_and_recheck(task)

    except Exception as error:

        st.session_state.git_message = ("warning", t("packages.failed", reason=error))

        st.rerun()

    st.session_state.task = checked

    st.session_state.git_message = ("success", t("packages.done", names=names))

    st.rerun()


def revision_panel(task) -> None:
    """The third answer, between accepting and rejecting.

    A finding worth fixing used to mean rejecting good code
    and paying for all of it again, and a human had no way
    to say anything of their own.
    """

    if (
        task.status != TaskStatus.WAITING_FOR_APPROVAL
        or task.git_operation.committed
        or not task.generated_files
    ):
        return

    st.markdown(f"**{t('revise.heading')}**")

    st.caption(t("revise.caption"))

    findings = [
        *[f"BLOCKER: {item}" for item in task.blockers],
        *[f"WARNING: {item}" for item in task.warnings],
        *[f"SUGGESTION: {item}" for item in task.suggestions],
    ]

    chosen = st.multiselect(
        t("revise.findings"),
        findings,
        key=f"revise-findings-{task.id}",
    )

    notes = st.text_area(
        t("revise.notes"),
        key=f"revise-notes-{task.id}",
        placeholder=t("revise.placeholder"),
    )

    if not st.button(
        t("revise.send"),
        key=f"revise-{task.id}",
        disabled=(not chosen and not notes.strip()) or shared.month_blocked,
    ):
        return

    feedback = "\n".join(
        [
            *[line for line in notes.strip().splitlines() if line.strip()],
            *chosen,
        ]
    )

    try:

        with st.spinner(t("revise.running")):
            revised = revise_task(task, feedback)

    except Exception as error:

        st.session_state.git_message = (
            "warning",
            t("revise.failed", reason=error),
        )

        st.rerun()

    st.session_state.task = revised

    st.session_state.git_message = ("success", t("revise.done"))

    st.rerun()


def decision_buttons(task) -> None:
    """The two final answers, side by side, and a free check again."""

    check_again_button(task)

    col1, col2 = st.columns(2)

    with col1:

        accept_button(task)

    with col2:

        reject_button(task)


def check_again_button(task) -> None:
    """The compiler and the tests again, on the files as they are: free."""

    if task.git_operation.committed or task.status != TaskStatus.WAITING_FOR_APPROVAL:
        return

    if not st.button(t("task.check_again"), key=f"check-again-{task.id}", help=t("task.check_again_help")):
        return

    with st.spinner(t("task.checking_again")):
        checked = shared.orchestrator.check_again(task)

    repository.save(checked)

    st.session_state.task = checked

    st.session_state.git_message = (
        "success" if checked.recommendation.value == "APPROVE" else "warning",
        t(
            "task.checked_again",
            compile=checked.compile_result.status.value,
            tests=checked.test_result.summary,
            verdict=checked.recommendation.value,
        ),
    )

    st.rerun()


def accept_button(task) -> None:
    """Approve: commit on the plan's branch, or retry the commit."""

    # Approval never fails because of git, so an approved
    # task can still lack its commit; pressing again
    # retries it. Only a commit that exists ends it.
    if st.button(
        t("task.approve"),
        disabled=task.git_operation.committed,
    ):

        # The git agent only ever runs once the human
        # has approved, and never pushes.
        try:

            operation = accept_record(task)

            st.session_state.git_message = (
                "success",
                (
                    "Committed "
                    f"{operation.short_hash} to "
                    f"{operation.branch_name}"
                ),
            )

        except GitError as error:

            st.session_state.git_message = (
                "warning",
                f"Approved, but not committed: {error}",
            )

        st.rerun()


def reject_button(task) -> None:
    """Reject: undo the files and reopen the task in its plan."""

    # Once committed, rejecting cannot take the commit
    # back; roll_back refuses it too, this just says so
    # before the click.
    committed = task.git_operation.committed

    if committed:

        st.caption(
            t(
                "task.reject_committed",
                hash=task.git_operation.short_hash,
            )
        )

    if st.button(t("task.reject"), disabled=committed):

        # Files first: a rejection that leaves the code
        # on disk hands it to the next task as if it
        # were part of the project.
        try:

            undone = roll_back(task)

            st.session_state.git_message = (
                "success",
                t(
                    "task.rolled_back",
                    removed=len(undone.removed),
                    restored=len(undone.restored),
                )
                + (
                    " "
                    + t(
                        "task.rollback_kept",
                        names=", ".join(undone.kept),
                    )
                    if undone.kept
                    else ""
                ),
            )

        except (GitError, ValueError, OSError) as error:

            st.session_state.git_message = (
                "warning",
                t("task.rollback_failed", reason=error),
            )

            st.rerun()

        later = [
            other
            for other in repository.get_all()
            if task.branch
            and other.branch == task.branch
            and other.created_at > task.created_at
            and other.status
            == TaskStatus.WAITING_FOR_APPROVAL
        ]

        if later:

            kind, text = st.session_state.git_message

            st.session_state.git_message = (
                "warning",
                text
                + " "
                + t("task.later_on_branch", count=len(later)),
            )

        reopen_in_plan(task)

        task.status = TaskStatus.REJECTED

        repository.update_status(
            task.id,
            TaskStatus.REJECTED,
        )

        st.rerun()
