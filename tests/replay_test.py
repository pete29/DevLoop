"""Offline replay of the datepicker run that failed, against a real compiler.

The model's answers are scripted as they came that day; the
orchestrator, the structural checks, QA's clean-up and the
TypeScript compiler are the real ones, on a throwaway
project. No model is called.

The compiler is borrowed from a project that has TypeScript
and Vitest installed: DEVLOOP_TYPESCRIPT_HOME names it, or
a sibling folder of this repository that has both is used.
Without one the replay is skipped, not failed:

    python -m tests.replay_test
"""

import json
import os
import shutil
import sys
import tempfile

os.environ["DEVLOOP_DATABASE"] = os.path.join(tempfile.mkdtemp(), "replay.db")

from config.settings import Settings  # noqa: E402
from models.architecture_review import ArchitectureReview  # noqa: E402
from models.compile_result import CompileStatus  # noqa: E402
from models.file_type import FileType  # noqa: E402
from models.generated_file import GeneratedFile  # noqa: E402
from models.test_result import TestResult, TestStatus  # noqa: E402
from agents.test_execution_agent import TestExecutionAgent  # noqa: E402
from services.git_diff_service import GitDiffService  # noqa: E402
from workflows.review_decision import ReviewDecision  # noqa: E402
from workflows.workflow_orchestrator import WorkflowOrchestrator  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


def installed(folder: str) -> bool:

    modules = os.path.join(folder, "node_modules")

    return os.path.isfile(os.path.join(modules, "typescript", "lib", "tsc.js")) and os.path.isdir(
        os.path.join(modules, "vitest")
    )


def find_typescript() -> str:
    """A node_modules with TypeScript and Vitest, or ""."""

    named = os.getenv("DEVLOOP_TYPESCRIPT_HOME", "")

    if named:
        return os.path.join(named, "node_modules") if installed(named) else ""

    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    parent = os.path.dirname(here)

    for name in sorted(os.listdir(parent)):

        candidate = os.path.join(parent, name)

        if candidate != here and os.path.isdir(candidate) and installed(candidate):
            return os.path.join(candidate, "node_modules")

    return ""


def link(target: str, link_path: str) -> None:
    """node_modules borrowed, not copied: a junction on Windows."""

    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(target, link_path)

    else:
        os.symlink(target, link_path, target_is_directory=True)


def write(root: str, path: str, content: str) -> None:

    target = os.path.join(root, path)

    os.makedirs(os.path.dirname(target), exist_ok=True)

    with open(target, "w", encoding="utf-8") as handle:
        handle.write(content)


# ------------------------------------------------------------ the scripted model

# The day's first wrong turn: an ES module import of a
# TypeScript file, by its compiled name.
DAYS = GeneratedFile(
    "src/days.ts",
    FileType.SOURCE,
    'import type { CalendarDate } from "./types.js";\n'
    "\n"
    "export function addDays(date: CalendarDate, n: number): CalendarDate {\n"
    "  const next = new Date(`${date}T00:00:00Z`);\n"
    "  next.setUTCDate(next.getUTCDate() + n);\n"
    "  return next.toISOString().slice(0, 10) as CalendarDate;\n"
    "}\n",
)

# The second: a sentence above the suite.
SUITE = (
    "import { describe, it, expect } from '../src/days' is not allowed, so the imports are as follows.\n"
    "\n"
    "import { describe, it, expect } from 'vitest';\n"
    "import { addDays } from '../src/days';\n"
    "import type { CalendarDate } from '../src/types';\n"
    "\n"
    "describe('addDays', () => {\n"
    "  it('crosses a month', () => {\n"
    "    expect(addDays('2024-01-31' as CalendarDate, 1)).toBe('2024-02-01');\n"
    "  });\n"
    "});\n"
)

# The third: a suite an earlier task left broken.
BROKEN_EARLIER = "This suite checks the types, as follows.\nimport { describe } from 'vitest';\n"

CALLS: list[str] = []


class Developer:
    def execute(self, task, repository_path=""):
        CALLS.append("developer")
        return [DAYS]

    def improve(self, task, files, brief, repository_path=""):
        CALLS.append("improve")
        return files


class Architect:
    def execute(self, task, files, history, repository_path=""):
        CALLS.append("architect")
        return ArchitectureReview(score=90, recommendation=ReviewDecision.APPROVE, review="Fine.")


class ScriptedLLM:
    def generate_text(self, prompt: str) -> str:
        CALLS.append("qa")
        return SUITE

    def generate_code(self, prompt: str) -> str:
        return ""


# ------------------------------------------------------------ the replay

modules = find_typescript()

if not modules:
    print("SKIPPED: no project with TypeScript and Vitest installed to borrow;")
    print("set DEVLOOP_TYPESCRIPT_HOME to one to run the replay.")
    raise SystemExit(0)

root = tempfile.mkdtemp()

try:

    link(modules, os.path.join(root, "node_modules"))

    write(
        root,
        "tsconfig.json",
        json.dumps(
            {
                "compilerOptions": {
                    "target": "ES2022",
                    "module": "ESNext",
                    "moduleResolution": "bundler",
                    "strict": True,
                    "skipLibCheck": True,
                    "noEmit": True,
                },
                "include": ["src", "tests"],
            }
        ),
    )

    write(root, "package.json", '{"type": "module"}')

    write(root, "src/types.ts", 'export type CalendarDate = string & { readonly __brand: "CalendarDate" };\n')

    write(root, "tests/types.test.ts", BROKEN_EARLIER)

    Settings.AUTO_BOOTSTRAP = False

    Settings.GENERATE_FILE_BY_FILE = True

    GitDiffService.compare = staticmethod(lambda root, paths: [])

    TestExecutionAgent.execute = staticmethod(
        lambda path: TestResult(status=TestStatus.PASSED, total_tests=1)
    )

    import services.llm_factory as factory

    factory.LLMFactory.create = classmethod(lambda cls, role="": ScriptedLLM())

    from agents.qa_agent import QAAgent

    orchestrator = WorkflowOrchestrator()

    orchestrator.developer = Developer()

    orchestrator.architect = Architect()

    orchestrator.qa = QAAgent()

    task = orchestrator.execute("Implement day arithmetic.", "", root)

    print("=" * 80)
    print("THE DAY'S THREE MISTAKES, REPLAYED")
    print("=" * 80)

    check(
        "'./types.js' is read as src/types.ts: no fix round, no copy",
        ("improve" in CALLS, sorted(n for n in os.listdir(root) if n.endswith(".js"))),
        (False, []),
    )

    with open(os.path.join(root, "tests", "days.test.ts"), encoding="utf-8") as handle:
        first_line = handle.readline().strip()

    check("the sentence above the suite is gone", first_line, "import { describe, it, expect } from 'vitest';")

    check(
        "the earlier task's broken suite is not this task's: it compiles",
        (task.compile_result.status, "before this task" in task.compile_result.reason),
        (CompileStatus.PASSED, True),
    )

    check("so the task is approvable", task.recommendation, ReviewDecision.APPROVE)

    check("and nobody was paid to fix anything", CALLS, ["developer", "architect", "qa"])

finally:
    junction = os.path.join(root, "node_modules")

    # The link only: never what it points at.
    if os.path.lexists(junction):
        os.unlink(junction) if sys.platform != "win32" else os.rmdir(junction)

    shutil.rmtree(root, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL REPLAY CHECKS PASSED")
print("=" * 80)
