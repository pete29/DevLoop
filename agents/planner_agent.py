from models.plan import Plan
from models.task_breakdown import Priority, TaskBreakdown
from services.file_parser import FileParseError, FileParser
from services.llm_factory import LLMFactory
from services.plan_validator import PlanValidator, clean_path
from services.repository_context import describe
from services.repository_survey import survey

MAX_TASKS = 12

PROMPT = """
You are a Technical Planner.

Break this epic into the smallest set of tasks a
developer can build one at a time.

Epic:
{epic}
{repository}
{code}
Rules:

- between 2 and {maximum} tasks
- each task is one deliverable a developer can
  finish on its own
- order them so a task only depends on tasks
  before it
- interfaces and contracts come before the
  code that implements them
- do not plan test files: a suite is written for
  every source file as part of the task that
  creates it, so a task for tests is work that
  has already happened
- a dependency is the id of an earlier task
- priority is HIGH, MEDIUM or LOW:
  foundational abstractions, interfaces and
  contracts are HIGH; implementations and
  providers are MEDIUM; everything else is LOW
- do not plan deployment, infrastructure or
  documentation unless the epic asks for it
- do not plan project setup: creating
  package.json, a tsconfig, a test config or a
  folder structure is handled before you, and a
  task for it would run the whole pipeline to
  write a file that already exists
- read the files already in the repository: do
  not plan work they already do, and build on
  what they export instead of redefining it
- for every task list the source files it
  creates and the existing files it modifies,
  as paths relative to the repository root;
  never list test files
- a task that modifies a file another task
  creates depends on that task

Return only JSON in exactly this shape:

{{
  "files": [
    {{
      "path": "1",
      "content": "Create the notification interface",
      "description": "Define the Notification contract every provider implements.",
      "priority": "HIGH",
      "dependencies": [],
      "creates": ["src/example-contract.ts"],
      "modifies": []
    }},
    {{
      "path": "2",
      "content": "Create the email provider",
      "description": "Implement the Notification contract for email.",
      "priority": "HIGH",
      "dependencies": [1],
      "creates": ["src/example-provider.ts"],
      "modifies": ["src/example-index.ts"]
    }}
  ]
}}

"path" is the task id as a string, "content" is
the title. No explanations outside the JSON.
"""


CONTINUE = """
This requirement already has a plan, and part of it
is done. These tasks are committed on the plan's
branch, and their code is in the repository below:

{done}

Plan only what the requirement still needs. Do not
plan any of the tasks above again, nor anything the
repository already does. Number the new tasks from
{start}. A new task may depend on a task above by its
id.
"""


def done_section(done: list[TaskBreakdown]) -> str:

    if not done:
        return "- (none yet)"

    return "\n".join(
        f"- {item.id}. {item.title}"
        + (f" (created {', '.join(item.creates)})" if item.creates else "")
        for item in done
    )


def order_tasks(
    tasks: list[TaskBreakdown],
) -> list[TaskBreakdown]:
    """Dependencies first, then priority, then id.

    A dependency cycle cannot be ordered, so the tasks
    caught in it are appended at the end rather than
    dropped or looped over.
    """

    remaining = list(tasks)

    known = {item.id for item in tasks}

    ordered: list[TaskBreakdown] = []

    placed: set[int] = set()

    while remaining:

        ready = [
            item
            for item in remaining
            if all(
                dependency in placed
                or dependency not in known
                for dependency in item.dependencies
            )
        ]

        if not ready:
            # Everything left is in a cycle.
            ordered.extend(
                sorted(
                    remaining,
                    key=lambda item: (
                        item.priority.rank,
                        item.id,
                    ),
                )
            )

            break

        ready.sort(
            key=lambda item: (item.priority.rank, item.id)
        )

        chosen = ready[0]

        ordered.append(chosen)

        placed.add(chosen.id)

        remaining.remove(chosen)

    return ordered


def find_cycles(
    tasks: list[TaskBreakdown],
) -> list[int]:
    """Ids that cannot be reached in dependency order."""

    known = {item.id for item in tasks}

    placed: set[int] = set()

    changed = True

    while changed:

        changed = False

        for item in tasks:

            if item.id in placed:
                continue

            if all(
                dependency in placed
                or dependency not in known
                for dependency in item.dependencies
            ):
                placed.add(item.id)

                changed = True

    return sorted(known - placed)


class PlannerAgent:
    """Turns an epic into tasks the pipeline can run.

    The model proposes the breakdown; the ordering,
    the dependency checks and the cycle detection are
    decided here, because they are facts about the graph
    rather than matters of judgement.
    """

    def __init__(self) -> None:

        self.llm = LLMFactory.create("planner")

    def execute(
        self,
        epic: str,
        repository_id: str = "",
        repository_path: str = "",
    ) -> Plan:

        # The same requirement is different work in an
        # empty folder and in a running project. Without
        # this the planner assumed one baseline and
        # produced "Initialize Node project" as a task,
        # which then ran the whole pipeline -- developer,
        # architect, QA, test gate -- for twenty-three
        # minutes to make a file a template writes
        # instantly.
        context = describe(repository_path)

        # The files themselves, not only how many there
        # are. A second plan for an issue planned again
        # what the first had built, because the planner
        # knew the folder held seven source files and not
        # which ones.
        found = survey(repository_path)

        print("=" * 80)
        print("REPOSITORY CONTEXT")
        print("=" * 80)
        print(context.summary())
        print("=" * 80)

        raw = self.llm.generate_text(
            PROMPT.format(
                epic=epic,
                maximum=MAX_TASKS,
                repository=(
                    chr(10) + context.render() + chr(10)
                    if repository_path
                    else ""
                ),
                code=(
                    "Files already in the repository:"
                    + chr(10)
                    + found.render()
                    + chr(10)
                    + found.render_referenced(epic)
                    if repository_path and not found.empty
                    else ""
                ),
            )
        )

        try:
            entries = self._entries(raw)

        except (FileParseError, ValueError) as error:
            raise RuntimeError(
                f"PlannerAgent returned no usable plan: {error}"
            ) from error

        tasks, issues = self._to_tasks(entries)

        if not tasks:
            raise RuntimeError(
                "PlannerAgent returned no usable tasks."
            )

        tasks = order_tasks(tasks)

        issues.extend(
            PlanValidator.check(tasks, set(found.files))
        )

        cycles = find_cycles(tasks)

        if cycles:
            issues.append(
                "Circular dependency between tasks "
                + ", ".join(str(item) for item in cycles)
                + ". They cannot be ordered, so they are "
                "listed last."
            )

        print("=" * 80)
        print(f"PLANNER RESULT ({len(tasks)} task(s))")
        print("=" * 80)

        for item in tasks:
            print(
                f"  {item.id}. [{item.priority.value}] "
                f"{item.title} "
                f"after={item.dependencies or '-'}"
            )

        for issue in issues:
            print(f"  ! {issue}")

        print("=" * 80)

        return Plan(
            repository_id=repository_id,
            epic=epic,
            tasks=tasks,
            issues=issues,
        )

    def extend(
        self,
        plan: Plan,
        repository_path: str = "",
    ) -> tuple[list[TaskBreakdown], list[str]]:
        """What the plan still needs, given what it has done.

        The tasks a plan finished stay; the ones that never
        did are planned again from the requirement, the
        code on the branch and the list of what is done.
        Returns the plan's new task list -- done tasks
        first, then the new ones, numbered on from them --
        and the problems found in it.
        """

        done = [item for item in plan.tasks if plan.is_done(item.id)]

        start = max([item.id for item in plan.tasks] or [0]) + 1

        context = describe(repository_path)

        found = survey(repository_path)

        raw = self.llm.generate_text(
            PROMPT.format(
                epic=plan.epic,
                maximum=MAX_TASKS,
                repository=(
                    chr(10) + context.render() + chr(10)
                    if repository_path
                    else ""
                ),
                code=(
                    "Files already in the repository:"
                    + chr(10)
                    + found.render()
                    + chr(10)
                    + found.render_referenced(plan.epic)
                    if repository_path and not found.empty
                    else ""
                )
                + CONTINUE.format(done=done_section(done), start=start),
            )
        )

        try:
            entries = self._entries(raw)

        except (FileParseError, ValueError) as error:
            raise RuntimeError(
                f"PlannerAgent returned no usable continuation: {error}"
            ) from error

        issues: list[str] = []

        done_ids = {item.id for item in done}

        added: list[TaskBreakdown] = []

        used = set(done_ids)

        for position, entry in enumerate(entries[:MAX_TASKS], start=start):

            if not isinstance(entry, dict):
                continue

            title = str(entry.get("content", "")).strip()

            if not title:
                continue

            task_id = self._identifier(entry, position, used)

            used.add(task_id)

            added.append(
                TaskBreakdown(
                    id=task_id,
                    title=title,
                    description=str(entry.get("description", "")).strip(),
                    priority=Priority.parse(entry.get("priority", "")),
                    dependencies=self._dependencies(entry, task_id, title, issues),
                    creates=self._paths(entry, "creates"),
                    modifies=self._paths(entry, "modifies"),
                )
            )

        # A dependency may name a done task or a new one;
        # anything else is the model's mistake, reported.
        known = done_ids | {item.id for item in added}

        for item in added:

            for dependency in [d for d in item.dependencies if d not in known]:
                issues.append(
                    f"Task {item.id} '{item.title}' depended on task "
                    f"{dependency}, which neither is done nor is planned. "
                    "That dependency was dropped."
                )

            item.dependencies = [d for d in item.dependencies if d in known]

        if not added:
            issues.append(
                "The planner found nothing left to do for this requirement."
            )

        tasks = done + order_tasks(added)

        issues.extend(PlanValidator.check(added, set(found.files)))

        return tasks, issues

    @staticmethod
    def _entries(raw: str) -> list[dict]:
        """The task objects, however the model wrapped them."""

        try:
            payload = FileParser.load(
                FileParser.extract_json(raw)
            )

            entries = payload.get("files")

            if isinstance(entries, list) and entries:
                return entries

        except (FileParseError, ValueError):
            pass

        salvaged = [
            value
            for value in FileParser.balanced_objects(raw)
            if "content" in value
        ]

        if salvaged:
            print(
                f"recovered {len(salvaged)} task(s) from "
                "an incomplete answer"
            )

            return salvaged

        raise FileParseError(
            "No task list in the answer."
        )

    @staticmethod
    def _to_tasks(
        entries: list[dict],
    ) -> tuple[list[TaskBreakdown], list[str]]:

        tasks: list[TaskBreakdown] = []

        issues: list[str] = []

        used: set[int] = set()

        for position, entry in enumerate(
            entries[:MAX_TASKS],
            start=1,
        ):

            if not isinstance(entry, dict):
                continue

            title = str(entry.get("content", "")).strip()

            if not title:
                continue

            task_id = PlannerAgent._identifier(
                entry,
                position,
                used,
            )

            used.add(task_id)

            tasks.append(
                TaskBreakdown(
                    id=task_id,
                    title=title,
                    description=str(
                        entry.get("description", "")
                    ).strip(),
                    priority=Priority.parse(
                        entry.get("priority", "")
                    ),
                    dependencies=PlannerAgent._dependencies(
                        entry,
                        task_id,
                        title,
                        issues,
                    ),
                    creates=PlannerAgent._paths(entry, "creates"),
                    modifies=PlannerAgent._paths(entry, "modifies"),
                )
            )

        return (
            PlannerAgent._drop_unknown(tasks, issues),
            issues,
        )

    @staticmethod
    def _paths(entry: dict, key: str) -> list[str]:
        """A task's file list, spelled one way, no repeats."""

        raw = entry.get(key) or []

        if not isinstance(raw, list):
            return []

        paths: list[str] = []

        for item in raw:

            path = clean_path(item)

            if path and path not in paths:
                paths.append(path)

        return paths

    @staticmethod
    def _identifier(
        entry: dict,
        position: int,
        used: set[int],
    ) -> int:

        try:
            value = int(str(entry.get("path", "")).strip())

        except (TypeError, ValueError):
            value = position

        if value <= 0 or value in used:
            value = position

        while value in used:
            value += 1

        return value

    @staticmethod
    def _dependencies(
        entry: dict,
        task_id: int,
        title: str,
        issues: list[str],
    ) -> list[int]:

        raw = entry.get("dependencies") or []

        if not isinstance(raw, list):
            return []

        found: list[int] = []

        for item in raw:

            try:
                value = int(str(item).strip())

            except (TypeError, ValueError):
                issues.append(
                    f"Task {task_id} '{title}' listed "
                    f"{item!r} as a dependency, which is "
                    "not a task id. It was ignored."
                )

                continue

            if value == task_id:
                issues.append(
                    f"Task {task_id} '{title}' depended "
                    "on itself. That dependency was "
                    "dropped."
                )

                continue

            if value not in found:
                found.append(value)

        return found

    @staticmethod
    def _drop_unknown(
        tasks: list[TaskBreakdown],
        issues: list[str],
    ) -> list[TaskBreakdown]:
        """Removes dependencies on tasks that do not exist."""

        known = {item.id for item in tasks}

        for item in tasks:

            unknown = [
                dependency
                for dependency in item.dependencies
                if dependency not in known
            ]

            for dependency in unknown:
                issues.append(
                    f"Task {item.id} '{item.title}' "
                    f"depended on task {dependency}, "
                    "which the plan does not contain. "
                    "That dependency was dropped."
                )

            item.dependencies = [
                dependency
                for dependency in item.dependencies
                if dependency in known
            ]

        return tasks
