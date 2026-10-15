from models.task_breakdown import TaskBreakdown
from services.repository_survey import is_test_path


def clean_path(path: str) -> str:
    """One spelling for a path, whatever the model wrote."""

    cleaned = str(path or "").strip().replace("\\", "/")

    while cleaned.startswith("./"):
        cleaned = cleaned[2:]

    return cleaned


def unsafe(path: str) -> bool:
    """Outside the repository, or not a path at all."""

    return (
        not path
        or path.startswith("/")
        or ":" in path
        or ".." in path.split("/")
    )


def ancestors(
    task: TaskBreakdown,
    by_id: dict[int, TaskBreakdown],
) -> set[int]:
    """Every task this one waits for, directly or not."""

    found: set[int] = set()

    pending = list(task.dependencies)

    while pending:

        current = pending.pop()

        if current in found or current not in by_id:
            continue

        found.add(current)

        pending.extend(by_id[current].dependencies)

    return found


class PlanValidator:
    """Checks a plan's file claims against the repository.

    The planner now says which files each task creates and
    which it modifies. Whether those claims hold is a fact
    about the folder and the dependency graph, so it is
    decided here and not asked of the model:

    - a file a task creates must not exist yet: if it does,
      the work is likely done already -- the second plan
      for an issue planned again what the first one built;
    - a file a task modifies must exist, or be created by a
      task it depends on;
    - modifying a file another task creates means waiting
      for that task;
    - two tasks do not create the same file;
    - tests are QA's, and paths stay inside the repository.

    Reports, never repairs: a plan built on a false
    assumption is the planner's mistake to show a human,
    not one to paper over by guessing what it meant.
    """

    @staticmethod
    def check(
        tasks: list[TaskBreakdown],
        existing: set[str],
    ) -> list[str]:

        problems: list[str] = []

        by_id = {task.id: task for task in tasks}

        creators: dict[str, int] = {}

        for task in tasks:

            for path in task.creates:

                if path in creators and creators[path] != task.id:
                    problems.append(
                        f"Tasks {creators[path]} and {task.id} "
                        f"both create {path}."
                    )

                creators.setdefault(path, task.id)

        for task in tasks:

            name = f"Task {task.id} '{task.title}'"

            for path in [*task.creates, *task.modifies]:

                if unsafe(path):
                    problems.append(
                        f"{name} names {path!r}, which is not "
                        "a path inside the repository."
                    )

                elif is_test_path(path):
                    problems.append(
                        f"{name} plans the test file {path}; "
                        "suites are written by QA for every "
                        "source file."
                    )

            for path in task.creates:

                if path in existing:
                    problems.append(
                        f"{name} creates {path}, which already "
                        "exists. That part may be done already; "
                        "check it before running the task."
                    )

            waits_for = ancestors(task, by_id)

            for path in task.modifies:

                if path in existing:
                    continue

                creator = creators.get(path)

                if creator is None:
                    problems.append(
                        f"{name} modifies {path}, which does not "
                        "exist and no task creates."
                    )

                elif creator != task.id and creator not in waits_for:
                    problems.append(
                        f"{name} modifies {path}, which task "
                        f"{creator} creates, but does not depend "
                        f"on task {creator}."
                    )

        return problems
