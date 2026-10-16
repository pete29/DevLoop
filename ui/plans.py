"""The plan view and its panels."""

import streamlit as st

from agents.pull_request_agent import PullRequestAgent
from config.settings import Settings
from models.plan_run import RunStatus
from models.pull_request_info import PullRequestState
from models.task_execution import ExecutionStatus
from models.task_status import TaskStatus
from services import ci_checks, costs, plan_branch, review_feedback
from services.environment_step import EnvironmentStep, assess, commit_scaffolding, write_scaffolding
from services.git_service import GitError, GitService
from services.github_service import GitHubError, parse_remote
from services.package_installer import blocked, install
from services.task_rollback import Rollback
from ui.actions import log_tail, plan_pull_request, plan_records, reject_plan, revise_task, start_run, waiting_records
from ui import shared
from ui.shared import plan_store, repository, repository_path_now, run_store, t


def plan_view() -> None:
    """The selected plan: Step 0, its branch and pull request, its tasks and runs."""

    if not st.session_state.plan:
        return

    # From the database, not the session: a worker writes
    # the plan's executions while this page shows it.
    plan = plan_store.get_by_id(st.session_state.plan.id) or st.session_state.plan

    st.session_state.plan = plan

    plan_header(plan)

    target_path = repository_path_now()

    # Step 0. Without it the first task ran in a folder
    # that could neither compile nor test what it was about
    # to pay for, and the plan looked as if project setup
    # had been skipped.
    environment = assess(target_path) if target_path else None

    skip_key = f"skip-environment-{plan.id}"

    environment_ok = environment is not None and (
        environment.ready
        or st.session_state.get(skip_key, False)
    )

    if environment is not None:
        environment_panel(target_path, environment, skip_key)

    branch_panel(plan, target_path)

    pull_request_panel(plan)

    # Runs happen in a worker process; the page only reads
    # them. While one is active, nothing else here may start
    # a task on the same branch.
    active_run = run_store.latest(plan.id)

    if active_run is not None and not active_run.status.active:
        active_run = None

    st.fragment(run_every=3 if active_run else None)(run_panel)(plan.id)

    over_budget = plan_cost_line(plan)

    plan_problems(plan)

    dependency_graph(plan)

    plan_dashboard(plan)

    execution_log(plan)

    plan_tasks(plan, active_run, environment_ok, over_budget, target_path)

    run_buttons(plan, active_run, environment_ok, over_budget, target_path)

    st.divider()


def plan_header(plan) -> None:
    """What the plan is for, a hint when it is large, what planning cost."""

    st.subheader(t("plan.planned_tasks"))

    st.caption(plan.epic)

    # A count, not a judgement: the human decides whether
    # the parts can ship apart.
    if len(plan.tasks) > Settings.SPLIT_HINT_TASKS:
        st.info(t("plan.split_hint", count=len(plan.tasks)))

    usage = st.session_state.get("plan_usage")

    if usage and usage[0] == plan.id and usage[1]:
        st.caption(t("plan.usage", usage=usage[1]))


def environment_panel(
    path: str,
    step: EnvironmentStep,
    skip_key: str,
) -> None:
    """Step 0 of the plan, one line per thing still missing.

    Every action is a button, because each is a different
    kind of act: writing templates touches only files, an
    install reaches the network, and a commit changes the
    repository's history.
    """

    with st.container(border=True):

        st.markdown(t("env.heading_ready") if step.ready else t("env.heading"))

        if not step.git:
            st.error(t("env.no_git"))

        identity_line(path, step)

        scaffolding_line(path, step)

        dependencies_line(path, step)

        scaffolding_commit_line(path, step)

        if not step.ready:
            st.checkbox(t("env.skip"), key=skip_key)


def identity_line(path: str, step: EnvironmentStep) -> None:
    """Who commits: without a name and an email git refuses every commit."""

    if not step.git or not step.identity_missing:
        return

    st.warning(t("env.identity_missing"))

    with st.form(f"env-identity-{path}", border=False):

        name = st.text_input(t("env.identity_name"))

        email = st.text_input(t("env.identity_email"))

        saved = st.form_submit_button(t("env.identity_save"))

    if not saved:
        return

    if not name.strip() or "@" not in email:
        st.error(t("env.identity_incomplete"))
        return

    try:
        GitService(path).set_identity(name, email)

        st.session_state.git_message = ("success", t("env.identity_saved", name=name.strip()))

    except GitError as error:
        st.session_state.git_message = ("warning", t("env.commit_failed", reason=error))

    st.rerun()


def scaffolding_line(path: str, step: EnvironmentStep) -> None:
    """The project files a plan needs, and writing the missing ones."""

    if not step.missing:
        st.write(t("env.scaffolding_ok"))
        return

    st.write(t("env.scaffolding_missing", names=", ".join(step.missing)))

    if st.button(t("env.create_scaffolding"), key=f"env-scaffold-{path}"):

        created = write_scaffolding(path)

        st.session_state.git_message = (
            "success",
            t("env.scaffolding_created", names=", ".join(created)),
        )

        st.rerun()


def dependencies_line(path: str, step: EnvironmentStep) -> None:
    """Whether the packages are installed, and installing them."""

    if not step.dependencies_missing:
        st.write(t("env.dependencies_ok"))
        return

    st.write(t("env.dependencies_missing"))

    # Nothing to install until package.json exists.
    if not step.missing:
        install_panel(path, "plan")


def scaffolding_commit_line(path: str, step: EnvironmentStep) -> None:
    """Committing the project files, once they are complete."""

    if not step.git:
        return

    if not step.uncommitted:

        if not step.missing:
            st.write(t("env.committed_ok"))

        return

    st.write(t("env.uncommitted", names=", ".join(step.uncommitted)))

    # After the install when there is one, so the lock file
    # goes into the same commit.
    waiting = step.identity_missing or bool(step.missing) or (
        step.dependencies_missing and not step.install_blocked
    )

    if not st.button(
        t("env.commit_scaffolding", branch=step.base_branch or "HEAD"),
        key=f"env-commit-{path}",
        disabled=waiting,
    ):
        return

    try:
        commit_hash = commit_scaffolding(path)

        st.session_state.git_message = ("success", t("env.committed", hash=commit_hash[:7]))

    except GitError as error:
        st.session_state.git_message = ("warning", t("env.commit_failed", reason=error))

    st.rerun()


def install_panel(path: str, where: str) -> None:
    """The one button that reaches the network.

    Everything else here either writes a file or talks to
    a remote this platform already had a token for.
    Installing packages fetches code and runs whatever
    postinstall scripts it carries, so the button says so
    rather than reading like a convenience.
    """

    refusal = blocked(path)

    if refusal and not Settings.ENABLE_PACKAGE_INSTALLATION:

        st.caption(t("install.switched_off"))

        return

    if refusal:

        st.caption(f"📦 {refusal}")

        return

    st.caption(t("install.warning"))

    if st.button(
        t("install.run"),
        # Two panels offer this, so the key says which.
        key=f"install-{where}-{path}",
    ):

        with st.spinner(t("install.spinner")):
            result = install(path)

        st.session_state.install_output = result.output

        st.session_state.git_message = (
            "success" if result.succeeded else "warning",
            result.message,
        )

        st.rerun()

    if st.session_state.get("install_output"):

        with st.expander(f"{t('install.output')} · {where}"):
            st.code(
                st.session_state.install_output,
                language="text",
            )


def branch_panel(plan, target_path: str) -> None:
    """Where the plan's work is in git, before any task runs.

    A plan for an issue that already had one continues on
    the same branch, and nothing said so: the new plan
    listed its tasks as never run while the branch beside
    it held the commits and the pull request.
    """

    branch = plan_branch.of(plan)

    service = GitService(target_path) if target_path else None

    if service is None or not service.is_repository():
        return

    local = service.branch_exists(branch)

    remote = service.ref_exists(f"refs/remotes/origin/{branch}")

    link = ""

    if remote:

        try:
            owner, name = parse_remote(service.remote_url())

            link = " · " + t(
                "branch.open_on_github",
                url=f"https://github.com/{owner}/{name}/tree/{branch}",
            )

        except (GitError, GitHubError):
            link = ""

    st.markdown(
        t(
            "branch.line",
            branch=branch,
            local="✅" if local else "—",
            remote="✅" if remote else "—",
        )
        + link
    )

    committed = [
        record
        for record in plan_records(plan)
        if record.git_operation.commit_hash
    ]

    if committed:
        st.caption(
            t(
                "branch.commits",
                count=len(committed),
                hashes=", ".join(
                    record.git_operation.short_hash
                    for record in committed
                ),
            )
        )

    earlier = [
        other
        for other in plan_store.get_all()
        if other.id != plan.id
        and other.created_at < plan.created_at
        and plan_branch.of(other) == branch
    ]

    if earlier:
        st.info(t("branch.continues", count=len(earlier)))


def pull_request_panel(plan) -> None:
    """The plan's pull request, and a way to ask GitHub.

    Merging is a human's act on GitHub, and nothing here
    hears about it on its own. The button reads it back,
    and a merged request is what moves the requirement to
    DELIVERED.
    """

    records = plan_records(plan)

    holder = plan_pull_request(records)

    if holder is None:

        if any(record.git_push.pushed for record in records):
            st.caption(t("plan.pr_none_pushed"))

        return

    info = holder.pull_request

    # A fifth of the width cut "Check the PR" to "Sprawdź sta…".
    left, right = st.columns([2, 1])

    with left:
        st.markdown(
            t(
                "plan.pr_line",
                label=info.label,
                state=info.state.value,
                url=info.url,
            )
        )

    with right:

        if st.button(
            t("plan.pr_refresh"),
            key=f"pr-refresh-{plan.id}",
            use_container_width=True,
        ):

            fresh = PullRequestAgent.refresh(holder)

            for record in records:
                repository.update_pull_request(record.id, fresh)

            st.session_state.git_message = (
                "success",
                t(
                    "plan.pr_refreshed",
                    label=fresh.label,
                    state=fresh.state.value,
                ),
            )

            st.rerun()

    # Feedback only matters while the request can change.
    if info.state == PullRequestState.OPEN:
        ci_panel(plan, holder, records)

        feedback_panel(plan, holder, records)


def ci_panel(plan, holder, records) -> None:
    """The PR's CI checks; a failure can be sent back to a task."""

    key = f"ci-{plan.id}"

    if st.button(t("ci.load"), key=f"{key}-load", use_container_width=True):

        try:
            st.session_state[key] = ci_checks.read(
                PullRequestAgent.service(holder),
                holder.pull_request.id,
            )

        except Exception as error:
            st.session_state[key] = None
            st.session_state.git_message = ("warning", t("ci.failed_to_read", reason=error))

        st.rerun()

    found = st.session_state.get(key)

    if not found:
        return

    head, runs = found

    if not runs:
        st.caption(t("ci.none"))
        return

    st.markdown(
        t(
            "ci.heading",
            sha=head[:7],
            passed=sum(1 for run in runs if run.status == "completed" and not run.failed),
            failed=sum(1 for run in runs if run.failed),
            pending=sum(1 for run in runs if run.status != "completed"),
        )
    )

    by_task = {}

    for item in plan.tasks:
        execution = plan.execution(item.id)
        record = next((r for r in records if execution and r.id == execution.task_record_id), None)
        if record is not None and record.generated_files:
            by_task[record.id] = f"{item.id}. {item.title}"

    for run in runs:

        st.markdown(f"{run.mark} [{run.name}]({run.url})" if run.url else f"{run.mark} {run.name}")

        if not run.failed or not by_task:
            continue

        with st.expander(t("ci.log", name=run.name)):

            tail_key = f"{key}-tail-{run.id}"

            if tail_key not in st.session_state:
                st.session_state[tail_key] = ci_checks.log_tail(
                    PullRequestAgent.service(holder),
                    run,
                )

            st.code(st.session_state[tail_key] or run.summary or "-", language="text")

            options = list(by_task)

            target = st.selectbox(
                t("feedback.task"),
                options,
                index=len(options) - 1,
                format_func=lambda record_id: by_task[record_id],
                key=f"{key}-task-{run.id}",
            )

            if st.button(t("ci.send"), key=f"{key}-send-{run.id}", type="primary"):

                try:
                    with st.spinner(t("feedback.spinner", task=by_task[target])):
                        revised = revise_task(
                            repository.get_by_id(target),
                            ci_checks.as_note(run, st.session_state[tail_key]),
                        )

                except Exception as error:
                    st.session_state.git_message = (
                        "warning",
                        t("feedback.partial", task=by_task[target], reason=error),
                    )
                    st.rerun()

                st.session_state.pop(key, None)

                st.session_state.task = revised

                st.session_state.git_message = (
                    "success",
                    t("ci.sent", name=run.name, task=by_task[target]),
                )

                st.rerun()


def feedback_panel(plan, holder, records) -> None:
    """Review comments from the plan's PR, sent back by choice.

    Read on a click, not on every redraw: each read is
    three calls to GitHub.
    """

    key = f"feedback-{plan.id}"

    load_feedback_button(holder, key)

    found = st.session_state.get(key)

    if found is None:
        return

    acted = set(plan.acted_comments)

    fresh = [comment for comment in found if comment.key not in acted]

    if not fresh:
        st.caption(t("feedback.none"))
        return

    by_task = revisable_tasks(plan, records)

    if not by_task:
        return

    chosen = feedback_choices(key, fresh, by_task, records)

    if chosen:
        send_feedback(plan, key, chosen, by_task)


def load_feedback_button(holder, key: str) -> None:
    """Reads the pull request's comments, on a click."""

    if not st.button(t("feedback.load"), key=f"{key}-load", use_container_width=True):
        return

    try:
        found = review_feedback.read(
            PullRequestAgent.service(holder),
            holder.pull_request.id,
        )

    except Exception as error:
        st.session_state.git_message = ("warning", t("feedback.failed", reason=error))
        found = None

    st.session_state[key] = found

    st.rerun()


def revisable_tasks(plan, records) -> dict[str, str]:
    """Record id to label, for each task with a version to revise.

    A comment can only go to a task that has one: the
    plan's records, latest per plan task.
    """

    by_task = {}

    for item in plan.tasks:
        execution = plan.execution(item.id)
        record = next(
            (r for r in records if execution and r.id == execution.task_record_id),
            None,
        )
        if record is not None and record.generated_files:
            by_task[record.id] = f"{item.id}. {item.title}"

    return by_task


def feedback_choices(key: str, fresh, by_task: dict[str, str], records) -> dict[str, list]:
    """Each comment, ticked or not, with the task it goes to.

    The comments to send, by record id -- once the send
    button is pressed; until then, nothing.
    """

    with st.expander(t("feedback.heading", count=len(fresh)), expanded=True):

        st.caption(t("feedback.caption"))

        chosen: dict[str, list] = {}

        options = list(by_task)

        for comment in fresh:

            with st.container(border=True):

                st.markdown(
                    f"**{comment.author}**"
                    + (f" · `{comment.where}`" if comment.where else "")
                    + (f" · [{comment.kind}]({comment.url})" if comment.url else f" · {comment.kind}")
                )

                st.write(comment.body)

                tick, owner = st.columns([1, 3])

                with tick:
                    picked = st.checkbox("✔", key=f"{key}-pick-{comment.key}")

                with owner:
                    guess = review_feedback.owner_of(comment, [r for r in records if r.id in by_task])
                    target = st.selectbox(
                        t("feedback.task"),
                        options,
                        index=options.index(guess) if guess in options else len(options) - 1,
                        format_func=lambda record_id: by_task[record_id],
                        key=f"{key}-task-{comment.key}",
                    )

                if picked:
                    chosen.setdefault(target, []).append(comment)

        count = sum(len(items) for items in chosen.values())

        if not st.button(
            t("feedback.send", count=count),
            key=f"{key}-send",
            disabled=not count,
            type="primary",
            use_container_width=True,
        ):
            return {}

    return chosen


def send_feedback(plan, key: str, chosen: dict[str, list], by_task: dict[str, str]) -> None:
    """Sends each task its comments, as a revision."""

    revised = None

    sent = 0

    for record_id, comments in chosen.items():

        record = repository.get_by_id(record_id)

        try:
            with st.spinner(t("feedback.spinner", task=by_task[record_id])):
                revised = revise_task(record, review_feedback.notes(comments))

        except Exception as error:
            st.session_state.git_message = (
                "warning",
                t("feedback.partial", task=by_task[record_id], reason=error),
            )
            break

        # Recorded per task as it succeeds: a later failure
        # must not offer these again.
        plan_store.mark_acted(plan.id, [comment.key for comment in comments])

        sent += len(comments)

    else:
        st.session_state.git_message = (
            "success",
            t("feedback.done", count=sent, tasks=len(chosen)),
        )

    st.session_state.pop(key, None)

    if revised is not None:
        st.session_state.task = revised

    st.rerun()


def run_panel(plan_id: str) -> None:
    """The plan's background run, redrawn while it works.

    A fragment refreshes this alone every few seconds; when
    the run ends, the whole page is redrawn once, so the
    dashboard, the tasks and the pull request catch up.
    """

    run = run_store.latest(plan_id)

    if run is None:
        return

    if not run.status.active:

        if st.session_state.watching_run == run.id:

            st.session_state.watching_run = None

            # A single task the human started: show it, as
            # the synchronous button used to.
            if run.task_id and run.produced:
                st.session_state.task = repository.get_by_id(run.produced[-1])

            st.rerun()

        if run.status != RunStatus.DONE or run.message:
            st.caption(
                t(
                    "run.ended",
                    status=run.status.value,
                    message=run.message or "",
                )
            )

        return

    st.session_state.watching_run = run.id

    # A task finished or another started: the whole page is
    # redrawn, so the task cards show it, not only this panel.
    progress = (run.current_task, len(run.produced))

    seen = st.session_state.get(f"run-progress-{run.id}")

    st.session_state[f"run-progress-{run.id}"] = progress

    if seen is not None and seen != progress:
        st.rerun()

    plan = plan_store.get_by_id(plan_id)

    item = plan.task(run.current_task) if plan and run.current_task else None

    st.info(
        t(
            "run.in_progress",
            status=run.status.value,
            task=f"{item.id}. {item.title}" if item else "—",
            done=len(run.produced),
            since=run.started_at[11:19],
        )
    )

    console = log_tail(run)

    if console:
        st.code(console, language="text")

    if run.status == RunStatus.RUNNING and st.button(
        t("plan.stop_after_task"),
        key=f"stop-run-{run.id}",
        use_container_width=True,
    ):
        run_store.request_stop(run.id)

        st.rerun()


def plan_cost_line(plan) -> bool:
    """What the plan has cost; whether it is over its limit."""

    plan_cost = costs.plan_spent(plan, repository.get_all())

    over_budget = costs.over_limit(plan_cost)

    st.caption(
        t(
            "cost.plan",
            spent=f"{plan_cost:.2f}",
            limit=(
                t("cost.of_limit", limit=f"{costs.limit():.2f}")
                if costs.limit() > 0
                else ""
            ),
        )
    )

    if over_budget:
        st.warning(t("cost.over_limit", limit=f"{costs.limit():.2f}"))

    return over_budget or shared.month_blocked


def plan_problems(plan) -> None:
    """What the planner's checks found wrong with the plan."""

    if plan.issues:

        st.warning(
            t("plan.problems", count=len(plan.issues))
        )

        for issue in plan.issues:
            st.write(f"- {issue}")


def dependency_graph(plan) -> None:
    """The tasks in layers: each layer runs once the ones above are done."""

    with st.expander(t("plan.dependency_graph")):

        levels = plan.levels()

        if not levels:

            st.write(t("plan.no_tasks"))

        for depth, layer in enumerate(levels, start=1):

            st.markdown(t("plan.step", n=depth))

            for item in layer:

                after = (
                    " ← "
                    + ", ".join(
                        str(d) for d in item.dependencies
                    )
                    if item.dependencies
                    else ""
                )

                done = "✅ " if plan.is_done(item.id) else ""

                st.write(
                    f"{done}`{item.id}` {item.title} "
                    f"[{item.priority.value}]{after}"
                )


def plan_dashboard(plan) -> None:
    """Progress, and the count of tasks in each state."""

    counts = plan.dashboard()

    st.progress(
        plan.percent_complete,
        text=t(
            "plan.progress",
            done=counts["COMPLETED"],
            total=counts["TOTAL"],
            percent=f"{plan.percent_complete * 100:.0f}",
        ),
    )

    (
        board_1,
        board_2,
        board_3,
        board_4,
        board_5,
        board_6,
    ) = st.columns(6)

    with board_1:
        st.metric(t("board.total"), counts["TOTAL"])

    with board_2:
        st.metric(t("board.completed"), counts["COMPLETED"])

    with board_3:
        st.metric(t("board.running"), counts["RUNNING"])

    with board_4:
        st.metric(t("board.ready"), counts["READY"])

    with board_5:
        st.metric(t("board.blocked"), counts["PENDING"])

    with board_6:
        st.metric(t("tests.failed"), counts["FAILED"])


def execution_log(plan) -> None:
    """What is running now, and what has run."""

    current = plan.running

    if current is not None:

        st.info(
            t(
                "plan.now_running",
                id=current.id,
                title=current.title,
            )
        )

    entries = plan.log()

    if entries:

        with st.expander(
            t("plan.log", count=len(entries)),
            expanded=current is not None,
        ):

            words = {
                "STARTED": ("▶️", t("log.started")),
                "COMPLETED": ("✅", t("log.completed")),
                "FAILED": ("❌", t("log.failed")),
                "RUNNING": ("⏳", t("log.running")),
            }

            for entry in entries:

                icon, verb = words.get(
                    entry.event, ("•", entry.event)
                )

                st.write(
                    t(
                        "log.entry",
                        at=entry.at[11:19],
                        icon=icon,
                        verb=verb,
                        id=entry.task_id,
                        title=entry.title,
                    )
                    + (
                        f" · {entry.detail}"
                        if entry.detail
                        else ""
                    )
                )


def plan_tasks(plan, active_run, environment_ok, over_budget, target_path) -> None:
    """Every planned task, in order."""

    marks = {
        ExecutionStatus.COMPLETED: "✅",
        ExecutionStatus.FAILED: "❌",
        ExecutionStatus.RUNNING: "⏳",
        ExecutionStatus.PENDING: "⛔",
        ExecutionStatus.READY: "▶️",
    }

    for item in plan.tasks:

        task_card(plan, active_run, environment_ok, over_budget, target_path, item, marks)


def queued_in_run(plan, item, record, active_run) -> bool:
    """Whether a running plan has yet to reach this task.

    Its last result is from before the run started -- a
    failure, a rejection -- and the run will do it again.
    Shown as that old failure, a plan running perfectly well
    looked as though nothing was happening.
    """

    if active_run is None or active_run.current_task == item.id:
        return False

    if active_run.task_id and active_run.task_id != item.id:
        return False

    if plan.status_of(item) == ExecutionStatus.COMPLETED and record and record.started_at >= active_run.started_at:
        return False

    return record is None or record.started_at < active_run.started_at


def task_card(plan, active_run, environment_ok, over_budget, target_path, item, marks) -> None:
    """One planned task: its state, its record, and how to run it."""

    blocked = plan.blocked_by(item)

    record = plan.execution(item.id)

    # The run writes a task's result when it ends, so while
    # it runs the stored status is still the last run's.
    if active_run is not None and active_run.current_task == item.id:
        status = ExecutionStatus.RUNNING

    else:
        status = plan.status_of(item)

    queued = queued_in_run(plan, item, record, active_run)

    label = t("run.queued_label") if queued else status.value

    with st.expander(
        f"{'🕒' if queued else marks[status]} {item.id}. {item.title} "
        f"[{item.priority.value}] · {label}",
        expanded=not queued
        and status
        in (
            ExecutionStatus.READY,
            ExecutionStatus.FAILED,
            ExecutionStatus.RUNNING,
        ),
    ):

        if queued:
            task_card_details(item, blocked)
            st.info(t("run.task_queued"))
            return

        task_card_details(item, blocked)

        task_card_record(plan, item, record)

        task_card_actions(plan, active_run, environment_ok, over_budget, target_path, item, record, status, blocked)


def task_card_details(item, blocked) -> None:
    """What the task is: its description, its files, what it depends on and waits for."""

    if item.description:
        st.write(item.description)

    if item.creates or item.modifies:
        st.caption(
            t(
                "plan.files",
                creates=", ".join(
                    f"`{path}`" for path in item.creates
                )
                or "—",
                modifies=", ".join(
                    f"`{path}`" for path in item.modifies
                )
                or "—",
            )
        )

    if item.dependencies:
        st.caption(
            t(
                "plan.depends_on",
                ids=", ".join(
                    str(d)
                    for d in item.dependencies
                ),
            )
        )

    if blocked:
        st.warning(
            t(
                "plan.waiting_for",
                ids=", ".join(
                    str(d) for d in blocked
                ),
            )
        )


def task_card_record(plan, item, record) -> None:
    """When it ran, and the review state of the record it produced."""

    if record and record.started_at:

        when = record.completed_at or record.started_at

        st.caption(
            f"{record.status.value} · {when[:19]}"
            + (
                f" · {record.duration}"
                if record.duration
                else ""
            )
        )

    # The run is one thing, the review another. A
    # plan said "done" for code nobody had looked at,
    # and the only way to that code was a sidebar
    # list of every task ever run.
    stored = (
        repository.get_by_id(record.task_record_id)
        if record and record.task_record_id
        else None
    )

    if stored is not None:

        review_left, review_right = st.columns([3, 1])

        with review_left:
            st.caption(
                t("plan.review_committed", hash=stored.git_operation.short_hash)
                if stored.git_operation.commit_hash
                else t("plan.review_rejected")
                if stored.status == TaskStatus.REJECTED
                else t("plan.review_waiting")
            )

        with review_right:

            if st.button(
                t("plan.open_task"),
                key=f"open-task-{plan.id}-{item.id}",
                use_container_width=True,
            ):

                st.session_state.task = stored

                st.rerun()


def task_card_actions(plan, active_run, environment_ok, over_budget, target_path, item, record, status, blocked) -> None:
    """Done, failed or running, and the button that runs it."""

    if status == ExecutionStatus.COMPLETED:

        st.success(t("plan.done"))

    else:

        if status == ExecutionStatus.FAILED:

            st.error(
                t(
                    "plan.failed",
                    reason=record.error,
                )
            )

        elif status == ExecutionStatus.RUNNING:

            if active_run is not None and active_run.current_task == item.id:
                st.info(t("run.task_in_progress"))

            else:
                st.warning(
                    t("plan.marked_running")
                )

        if st.button(
            t("plan.run_again")
            if status
            in (
                ExecutionStatus.FAILED,
                ExecutionStatus.RUNNING,
            )
            else t("plan.run_task"),
            key=f"run-{plan.id}-{item.id}",
            disabled=bool(blocked)
            or not target_path
            or not environment_ok
            or active_run is not None
            or over_budget,
        ):

            start_run(plan, target_path, item.id)


def run_buttons(plan, active_run, environment_ok, over_budget, target_path) -> None:
    """Run the whole plan, or close it."""

    ready = [
        item
        for item in plan.remaining
        if plan.is_ready(item)
    ]

    if target_path and not environment_ok:
        st.info(t("env.runs_blocked"))

    run_all, clear = st.columns(2)

    with run_all:

        run_all_button(plan, active_run, environment_ok, over_budget, target_path, ready)

    with clear:

        close_plan_button()

    if active_run is None:
        reject_plan_panel(plan)


def reject_plan_panel(plan) -> None:
    """Reject every waiting task of the plan, after a confirmation."""

    waiting = waiting_records(plan)

    if not waiting:
        return

    with st.expander(t("plan.reject_all", count=len(waiting))):

        st.caption(t("plan.reject_all_caption"))

        sure = st.checkbox(t("plan.reject_all_sure"), key=f"reject-all-sure-{plan.id}")

        if not st.button(
            t("plan.reject_all_button", count=len(waiting)),
            key=f"reject-all-{plan.id}",
            disabled=not sure,
            use_container_width=True,
        ):
            return

        try:
            count, undone = reject_plan(plan)

            st.session_state.git_message = ("success", rejected_message(count, undone))

        except (GitError, ValueError, OSError) as error:
            st.session_state.git_message = ("warning", t("task.rollback_failed", reason=error))

        st.session_state.plan = plan_store.get_by_id(plan.id)

        st.rerun()


def rejected_message(count: int, undone: Rollback) -> str:

    return t(
        "plan.rejected_all",
        count=count,
        removed=len(undone.removed),
        restored=len(undone.restored),
    ) + (
        " " + t("task.rollback_kept", names=", ".join(undone.kept))
        if undone.kept
        else ""
    )


def run_all_button(plan, active_run, environment_ok, over_budget, target_path, ready) -> None:
    """Run the whole plan in the background."""

    if active_run is None and st.button(
        t("plan.run_all", count=len(plan.remaining)),
        disabled=not ready
        or not target_path
        or not environment_ok
        or over_budget,
        use_container_width=True,
    ):

        start_run(plan, target_path)

    if active_run is None:
        estimate_line(len(plan.remaining))


def estimate_line(remaining: int) -> None:
    """What running the rest will likely cost, from recent tasks."""

    guess = costs.estimate(remaining, repository.get_all())

    if guess is None:
        return

    st.caption(
        t(
            "cost.estimate",
            total=f"{guess.total:.2f}",
            low=f"{guess.total_low:.2f}",
            high=f"{guess.total_high:.2f}",
            tasks=guess.tasks,
            each=f"{guess.typical:.2f}",
            sample=guess.sample,
        )
    )


def close_plan_button() -> None:
    """Close the plan."""

    if st.button(
        t("plan.close"),
        use_container_width=True,
    ):

        st.session_state.plan = None

        st.rerun()
