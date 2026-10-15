"""Offline checks for the order the pipeline spends money in.

Every agent is faked, and so are the compiler and the test
runner, so this runs with no model, no node and no network:

    python -m tests.orchestrator_test

What it pins down: the free checks run before the
architect, a fix after failing tests rewrites only the
suites it has to, a file the run dropped is removed, and
every run says what it cost.
"""

import os
import shutil
import tempfile

import services.llm_factory as factory
from agents.test_execution_agent import TestExecutionAgent
from config.settings import Settings
from models.architecture_review import ArchitectureReview
from models.compile_result import CompileResult, CompileStatus
from models.file_type import FileType
from models.generated_file import GeneratedFile
from models.test_result import TestResult, TestStatus
from services import type_checker, usage_ledger
from services.git_diff_service import GitDiffService
from workflows.review_decision import ReviewDecision
from workflows.workflow_orchestrator import (
    WorkflowOrchestrator,
)

failures: list[str] = []


def check(
    label: str,
    actual: object,
    expected: object,
) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


class NoLLM:
    def generate_text(self, prompt: str) -> str:
        raise AssertionError("no agent here may reach a model")


factory.LLMFactory.create = classmethod(
    lambda cls, role="": NoLLM()
)

Settings.AUTO_BOOTSTRAP = False

Settings.MAX_REVIEW_LOOPS = 3

Settings.MAX_TEST_LOOPS = 1

Settings.MAX_GATE_FIXES = 2

GitDiffService.compare = staticmethod(lambda root, paths: [])


def source(path: str, content: str) -> GeneratedFile:

    return GeneratedFile(
        path=path,
        file_type=FileType.SOURCE,
        content=content,
    )


A = source("src/a.ts", "export const a = 1;")

B = source("src/b.ts", "export const b = 2;")

B_FIXED = source("src/b.ts", "export const b = 3;")

# Everything that happened, in order, across the fakes.
CALLS: list[str] = []


class Developer:
    def __init__(self, first, revisions):
        self.first = first
        self.revisions = list(revisions)
        self.briefs: list[str] = []

    def execute(self, task, repository_path=""):
        CALLS.append("developer")
        usage_ledger.record(
            usage_ledger.Usage(
                role="developer",
                model="claude-sonnet-5-5",
                input_tokens=1000,
                output_tokens=500,
            )
        )
        return list(self.first)

    def improve(self, task, files, brief, repository_path=""):
        CALLS.append("improve")
        self.briefs.append(brief)
        return list(self.revisions.pop(0))


class Architect:
    def __init__(self, blockers_per_round=()):
        self.rounds = list(blockers_per_round)

    def execute(self, task, files, history, repository_path=""):
        CALLS.append("architect")
        blockers = self.rounds.pop(0) if self.rounds else []
        return ArchitectureReview(
            score=90 if not blockers else 40,
            recommendation=(
                ReviewDecision.REQUEST_CHANGES
                if blockers
                else ReviewDecision.APPROVE
            ),
            review="BLOCKER: " + "; ".join(blockers)
            if blockers
            else "Looks fine.",
            blockers=list(blockers),
        )


class QA:
    def __init__(self):
        self.only: list[object] = []

    def execute(self, files, only=None):
        CALLS.append("qa")
        self.only.append(only)
        return [
            GeneratedFile(
                path=f"tests/{item.path[4:-3]}.test.ts",
                file_type=FileType.TEST,
                content=f"// suite for {item.content}",
            )
            for item in files
            if only is None or item.path in only
        ]


def compiles(*statuses):
    """The compiler answers these, in order, then PASSED."""

    queue = list(statuses)

    def fake(repository_path):
        CALLS.append("tsc")
        status = queue.pop(0) if queue else CompileStatus.PASSED
        return CompileResult(
            status=status,
            output="src/b.ts(1,1): error TS2322: nope"
            if status == CompileStatus.FAILED
            else "",
        )

    type_checker.check = fake


def tests_report(*statuses):

    queue = list(statuses)

    def fake(repository_path):
        CALLS.append("vitest")
        status = queue.pop(0) if queue else TestStatus.PASSED
        return TestResult(status=status, output="1 failed")

    TestExecutionAgent.execute = staticmethod(fake)


def run(developer, architect, qa, root):

    CALLS.clear()

    orchestrator = WorkflowOrchestrator()

    orchestrator.developer = developer

    orchestrator.architect = architect

    orchestrator.qa = qa

    return orchestrator.execute("Build a and b.", "", root)


def step_names(task) -> list[str]:

    return [step.name for step in task.steps]


root = tempfile.mkdtemp()

try:

    print("=" * 80)
    print("THE COMPILER RUNS BEFORE THE ARCHITECT")
    print("=" * 80)

    compiles(CompileStatus.FAILED)
    tests_report()

    developer = Developer([A, B], [[A, B_FIXED]])

    task = run(developer, Architect(), QA(), root)

    check(
        "a file set that does not compile goes back "
        "without an architect call",
        CALLS[:5],
        ["developer", "tsc", "improve", "tsc", "architect"],
    )

    check(
        "and the developer is told what the compiler said",
        "TS2322" in developer.briefs[0],
        True,
    )

    check(
        "the architect reviews once, the fixed code",
        CALLS.count("architect"),
        1,
    )

    check(
        "the task is approvable",
        task.recommendation,
        ReviewDecision.APPROVE,
    )

    print()
    print("=" * 80)
    print("CODE THAT NEVER PASSES NEVER REACHES THE ARCHITECT")
    print("=" * 80)

    # Every fix the free checks may ask for, then once more
    # with the suites, and once after the test loop's fix.
    compiles(*[CompileStatus.FAILED] * (Settings.MAX_GATE_FIXES + 3))
    tests_report()

    developer = Developer([A, B], [[A, B], [A, B], [A, B]])

    task = run(developer, Architect(), QA(), root)

    check(
        "no architect call at all",
        CALLS.count("architect"),
        0,
    )

    check(
        "the free checks stop after their own fix budget",
        CALLS[: CALLS.index("qa")].count("improve"),
        Settings.MAX_GATE_FIXES,
    )

    check(
        "the review says why it is missing",
        task.architecture_review.startswith("Not reviewed."),
        True,
    )

    check(
        "and the task is not approvable",
        task.recommendation,
        ReviewDecision.REQUEST_CHANGES,
    )

    print()
    print("=" * 80)
    print("UNREVIEWED CODE IS NOT APPROVABLE EVEN IF IT COMPILES")
    print("=" * 80)

    # Fails every fix, then compiles once the suites are
    # written: clean in the end, but the architect never
    # read it.
    compiles(*[CompileStatus.FAILED] * (Settings.MAX_GATE_FIXES + 1))
    tests_report()

    task = run(
        Developer([A, B], [[A, B], [A, B]]),
        Architect(),
        QA(),
        root,
    )

    check(
        "the final compile passed",
        task.compile_result.status,
        CompileStatus.PASSED,
    )

    check(
        "and the recommendation still asks for changes",
        task.recommendation,
        ReviewDecision.REQUEST_CHANGES,
    )

    print()
    print("=" * 80)
    print("COMPILE ERRORS DO NOT USE UP THE ARCHITECT'S ROUNDS")
    print("=" * 80)

    # The real run this is from: a compile error, a review
    # with blockers, a fix that broke the compile again.
    # With one shared budget the blockers were never fixed.
    compiles(
        CompileStatus.FAILED,
        CompileStatus.PASSED,
        CompileStatus.FAILED,
    )
    tests_report()

    task = run(
        Developer([A, B], [[A, B], [A, B_FIXED], [A, B_FIXED]]),
        Architect([["Bypasses the PasswordRule contract"], []]),
        QA(),
        root,
    )

    check(
        "the architect gets its second round",
        CALLS.count("architect"),
        2,
    )

    check(
        "and the final review is of the final code",
        (task.blockers, task.recommendation),
        ([], ReviewDecision.APPROVE),
    )

    print()
    print("=" * 80)
    print("AN ARCHITECT BLOCKER STILL SENDS THE CODE BACK")
    print("=" * 80)

    compiles()
    tests_report()

    task = run(
        Developer([A, B], [[A, B_FIXED]]),
        Architect([["Hard-coded dependency"], []]),
        QA(),
        root,
    )

    check(
        "review, fix, free checks, review again",
        [
            call
            for call in CALLS
            if call in ("architect", "improve", "tsc")
        ][:5],
        ["tsc", "architect", "improve", "tsc", "architect"],
    )

    print()
    print("=" * 80)
    print("A FIX AFTER FAILING TESTS REWRITES ONLY ITS SUITES")
    print("=" * 80)

    compiles()
    tests_report(TestStatus.FAILED, TestStatus.PASSED)

    qa = QA()

    task = run(
        Developer([A, B], [[A, B_FIXED]]),
        Architect(),
        qa,
        root,
    )

    check(
        "the first QA run writes every suite",
        qa.only[0],
        None,
    )

    check(
        "the refresh asks only for the changed file",
        qa.only[1],
        {"src/b.ts"},
    )

    check(
        "no second architecture review after a test fix",
        CALLS.count("architect"),
        1,
    )

    check(
        "the untouched suite is kept",
        sorted(
            item.path
            for item in task.generated_files
            if item.path.startswith("tests/")
        ),
        ["tests/a.test.ts", "tests/b.test.ts"],
    )

    check(
        "and the rewritten one is the new one",
        [
            item.content
            for item in task.generated_files
            if item.path == "tests/b.test.ts"
        ],
        ["// suite for export const b = 3;"],
    )

    print()
    print("=" * 80)
    print("A FILE THE RUN DROPPED IS REMOVED")
    print("=" * 80)

    fresh = tempfile.mkdtemp()

    try:

        os.makedirs(os.path.join(fresh, "src"))

        keep = os.path.join(fresh, "src", "keep.ts")

        with open(keep, "w", encoding="utf-8") as handle:
            handle.write("export const keep = 0;")

        compiles(CompileStatus.FAILED)
        tests_report()

        KEEP = source("src/keep.ts", "export const keep = 1;")

        run(
            Developer([A, B, KEEP], [[A]]),
            Architect(),
            QA(),
            fresh,
        )

        check(
            "a file this run created and dropped is gone",
            os.path.exists(os.path.join(fresh, "src", "b.ts")),
            False,
        )

        check(
            "a file that existed before the run stays",
            os.path.exists(keep),
            True,
        )

    finally:
        shutil.rmtree(fresh, ignore_errors=True)

    print()
    print("=" * 80)
    print("EVERY RUN SAYS WHAT IT COST")
    print("=" * 80)

    compiles()
    tests_report()

    task = run(
        Developer([A], []),
        Architect(),
        QA(),
        root,
    )

    usage = [
        step.detail
        for step in task.steps
        if step.name == "step.usage"
    ]

    check(
        "a usage step is recorded",
        len(usage),
        1,
    )

    # 1000 in at $2/M + 500 out at $10/M = $0.007.
    check(
        "with the developer's tokens and the price",
        usage[0] if usage else "",
        "developer 1× 1.0k->500 $0.01 · total $0.01",
    )

    check(
        "an unpriced model is shown without a price",
        usage_ledger.describe(
            [usage_ledger.Usage(role="x", model="unknown")]
        ),
        "x 1× 0->0 · total ?",
    )

    check(
        "a local model is free",
        usage_ledger.Usage(
            model="qwen", input_tokens=10, free=True
        ).cost,
        0.0,
    )

    print()
    print("=" * 80)
    print("A HUMAN CAN SEND A TASK BACK WITH NOTES")
    print("=" * 80)

    compiles()
    tests_report()

    first = run(Developer([A, B], []), Architect(), QA(), root)

    CALLS.clear()

    reviser = Developer([], [[A, B_FIXED]])

    orchestrator = WorkflowOrchestrator()
    orchestrator.developer = reviser
    orchestrator.architect = Architect()
    orchestrator.qa = QA()

    revised = orchestrator.revise(
        first,
        "Use a Unicode class.\nWARNING: rule is ASCII only",
    )

    check(
        "the developer edits, it does not start over",
        CALLS[0],
        "improve",
    )

    check(
        "from the files on disk",
        sorted(item.path for item in first.generated_files)[:2],
        ["src/a.ts", "src/b.ts"],
    )

    brief = reviser.briefs[0] if reviser.briefs else ""

    check(
        "the notes arrive as blockers, every line",
        "- Use a Unicode class." in brief
        and "- WARNING: rule is ASCII only" in brief,
        True,
    )

    check(
        "and name the files when the notes name none",
        "Files under review: src/a.ts, src/b.ts" in brief,
        True,
    )

    check(
        "the notes become part of the task",
        revised.description.endswith(
            "Human review notes:\nUse a Unicode class.\n"
            "WARNING: rule is ASCII only"
        ),
        True,
    )

    check(
        "then the same checks and review run again",
        ("tsc" in CALLS, "architect" in CALLS, "qa" in CALLS),
        (True, True, True),
    )

    check(
        "the review history carries on",
        [entry.iteration for entry in revised.review_history],
        [1, 2],
    )

    check(
        "and the revision is reviewed, so it can be approved",
        revised.recommendation,
        ReviewDecision.APPROVE,
    )

    check(
        "the revised file is what is on disk",
        open(os.path.join(root, "src", "b.ts"), encoding="utf-8").read(),
        "export const b = 3;",
    )

    check(
        "files the first attempt created still count as created",
        set(first.created_files) <= set(revised.created_files),
        True,
    )

    print()
    print("=" * 80)
    print("A MISSING PACKAGE STOPS THE RUN, AND IS OFFERED")
    print("=" * 80)

    package_root = tempfile.mkdtemp()

    try:

        with open(os.path.join(package_root, "package.json"), "w", encoding="utf-8") as handle:
            handle.write('{"devDependencies": {"typescript": "^5"}}')

        USES_ZOD = source("src/schema.ts", 'import { z } from "zod";\nexport const s = z.string();')

        compiles(CompileStatus.FAILED)
        tests_report()

        stopped = run(Developer([USES_ZOD], []), Architect(), QA(), package_root)

        check(
            "the task asks for the package",
            (stopped.packages, "step.packages" in step_names(stopped)),
            (["zod"], True),
        )

        check(
            "and no fix, review, QA or test was paid for meanwhile",
            [call for call in CALLS if call in ("improve", "architect", "qa", "vitest")],
            [],
        )

        # The human installs it.
        os.makedirs(os.path.join(package_root, "node_modules", "zod"))

        with open(os.path.join(package_root, "node_modules", "zod", "package.json"), "w", encoding="utf-8") as handle:
            handle.write("{}")

        compiles()
        tests_report()

        CALLS.clear()

        rechecker = WorkflowOrchestrator()
        rechecker.developer = Developer([], [])
        rechecker.architect = Architect()
        rechecker.qa = QA()

        checked = rechecker.recheck(stopped)

        check(
            "checking again uses the same files: no developer call, then review, QA and tests",
            ("developer" in CALLS, "improve" in CALLS, "architect" in CALLS, "vitest" in CALLS),
            (False, False, True, True),
        )

        check(
            "and nothing is missing any more",
            (checked.packages, checked.recommendation),
            ([], ReviewDecision.APPROVE),
        )

    finally:
        shutil.rmtree(package_root, ignore_errors=True)

finally:
    shutil.rmtree(root, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL ORCHESTRATOR CHECKS PASSED")
print("=" * 80)
