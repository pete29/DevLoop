import os
from dataclasses import dataclass, field

from agents.architect_agent import ArchitectAgent
from agents.developer_agent import DeveloperAgent
from agents.qa_agent import QAAgent
from agents.test_execution_agent import TestExecutionAgent
from config.settings import Settings
from models.architecture_review import ArchitectureReview
from models.compile_result import CompileResult
from models.file_type import FileType
from models.file_generation_result import (
    FileGenerationResult,
)
from models.generated_file import GeneratedFile
from models.pipeline_step import StepRecorder
from models.review_history import (
    ReviewHistory,
)
from models.structure_report import StructureReport
from models.task import Task
from models.task_status import TaskStatus
from models.test_result import TestResult, TestStatus
from services import packages, type_checker, usage_ledger
from services.bootstrap import bootstrap
from services.file_parser import FileParser
from services.file_writer import FileWriter
from services.git_diff_service import GitDiffService
from services.repository_context import describe
from services.repository_survey import survey
from services.structure_validator import StructureValidator
from workflows.recommendation_policy import (
    RecommendationPolicy,
)
from workflows.review_decision import (
    ReviewDecision,
)


def describe_files(files: list[GeneratedFile]) -> str:
    """How much came back, for the step record."""

    return (
        f"{len(files)} file(s), "
        f"{sum(len(item.content) for item in files)} chars"
    )


HUMAN_NOTES = "Human review notes:"


def with_feedback(description: str, feedback: str) -> str:
    """The task as it stands after a human sent it back.

    Kept in the description, not beside it: the developer,
    the architect and every later round read the task, and
    a note they could not see would be overruled by the
    first review that disagreed with it.
    """

    return (
        f"{description.rstrip()}\n\n{HUMAN_NOTES}\n"
        f"{feedback.strip()}"
    )


def revision_brief(
    feedback: str,
    files: list[GeneratedFile],
) -> str:
    """What the developer acts on when a human sends work back.

    Phrased as blockers, because a human's request is not
    optional. The files are named when the notes name none:
    the developer rewrites only the files a brief mentions,
    and "use a Unicode class" names no file.
    """

    lines = [
        "BLOCKERS (from the human reviewer):",
        *[
            line if line.lstrip().startswith("-") else f"- {line}"
            for line in feedback.strip().splitlines()
            if line.strip()
        ],
    ]

    if not any(item.path in feedback for item in files):
        lines += [
            "",
            "Files under review: "
            + ", ".join(item.path for item in files),
        ]

    return "\n".join(lines)


def changed_paths(
    before: list[GeneratedFile],
    after: list[GeneratedFile],
) -> set[str]:
    """Paths that are new or whose content differs."""

    previous = {item.path: item.content for item in before}

    return {
        item.path
        for item in after
        if previous.get(item.path) != item.content
    }


@dataclass
class Gates:
    """The checks that cost nothing, run before any that do.

    The structural validator and the compiler answer in
    milliseconds and for free. The architect is the most
    expensive call in the run. Asking it to review a file
    set that does not compile, or imports a file that does
    not exist, paid for a review whose only possible
    outcome was "send it back" -- which the free checks had
    already decided.
    """

    report: StructureReport = field(
        default_factory=StructureReport
    )

    compile_result: CompileResult = field(
        default_factory=CompileResult
    )

    @property
    def passed(self) -> bool:

        return (
            not self.report.blockers
            and not self.compile_result.blocks_delivery
        )

    @property
    def detail(self) -> str:

        return (
            f"{len(self.report.blockers)}S · "
            f"tsc {self.compile_result.status.value}"
        )

    def brief(self) -> str:
        """What the developer has to fix, facts first."""

        parts: list[str] = []

        if self.report.blockers:
            parts.append(
                "Repository problems found by a "
                "compiler-style pass:\n"
                + "\n".join(
                    f"- {finding}"
                    for finding in self.report.blockers
                )
            )

        # A cycle told as prose went unfixed for three
        # rounds running: the developer rewrites one file
        # at a time and cannot see which import closes the
        # loop. The validator can, so it says which one to
        # remove instead of describing the route.
        cuts = self.report.cuts()

        if cuts:
            parts.append(
                "Do exactly this to break the cycles:\n"
                + "\n".join(f"- {cut}" for cut in cuts)
            )

        if self.compile_result.blocks_delivery:
            parts.append(self.compile_result.brief())

        return "\n\n".join(parts)


@dataclass
class RunFiles:
    """What this run has put on disk.

    Files are written before review now, so the compiler
    can see them, which means a file the developer drops in
    a later round would otherwise stay behind: compiled,
    surveyed, imported by the next task, and never
    committed. Only a file this run created is ever
    removed -- one that existed before is somebody's.
    """

    written: set[str] = field(default_factory=set)

    created: set[str] = field(default_factory=set)


class WorkflowOrchestrator:
    def __init__(
        self,
    ) -> None:

        self.developer = DeveloperAgent()

        self.architect = ArchitectAgent()

        self.qa = QAAgent()

    def execute(
        self,
        task_description: str,
        repository_id: str = "",
        repository_path: str = "",
    ) -> Task:

        spent = usage_ledger.mark()

        steps = StepRecorder()

        on_disk = RunFiles()

        created = self.prepare(repository_path)

        if created:
            steps.record(
                "step.bootstrap",
                ", ".join(created),
            )

        # What already fails to compile, and which tests
        # already fail, before this task writes anything:
        # neither is its to fix.
        baseline = type_checker.baseline(repository_path)

        test_baseline = TestExecutionAgent.baseline(repository_path)

        source_files = self.developer.execute(
            task_description,
            repository_path,
        )

        steps.record(
            "step.developer",
            describe_files(source_files),
        )

        if not source_files:

            raise RuntimeError("DeveloperAgent returned no files.")

        return self.finish(
            task_description,
            repository_id,
            repository_path,
            source_files,
            steps,
            on_disk,
            spent,
            created,
            baseline=baseline,
            test_baseline=test_baseline,
        )

    def revise(self, task: Task, feedback: str) -> Task:
        """The task again, from its own files, with a human's notes.

        Accept and reject were the only answers a human had:
        a warning worth fixing meant rejecting good code and
        paying for all of it again. Here the developer edits
        the files that are on disk, and the result goes
        through the same checks, review, tests and approval
        as the first attempt. The review history carries on,
        so the architect sees what it said before.
        """

        spent = usage_ledger.mark()

        steps = StepRecorder()

        root = task.repository_path

        sources: list[GeneratedFile] = []

        gone: list[str] = []

        for item in task.generated_files:

            if item.file_type != FileType.SOURCE:
                continue

            path = FileWriter.resolve(root, item.path)

            # Removed since -- rejecting a later task can take
            # a file this version also touched. One missing
            # file stopped the whole revision.
            if not os.path.isfile(path):
                gone.append(item.path)
                continue

            with open(path, encoding="utf-8") as handle:
                sources.append(
                    GeneratedFile(
                        path=item.path,
                        file_type=item.file_type,
                        content=handle.read(),
                    )
                )

        if not sources:
            raise RuntimeError(
                "The task's source files are no longer on disk."
            )

        if gone:
            steps.record("step.revision_gone", ", ".join(gone), ok=False)

        # The previous attempt's files are this run's: the
        # ones it created can still be dropped and removed,
        # and a reject of the revision deletes them.
        on_disk = RunFiles(
            written={item.path for item in task.generated_files},
            created=set(task.created_files),
        )

        description = with_feedback(task.description, feedback)

        source_files = self.developer.improve(
            description,
            sources,
            revision_brief(feedback, sources),
            root,
        )

        steps.record(
            "step.revision",
            describe_files(source_files),
        )

        return self.finish(
            description,
            task.repository_id,
            root,
            source_files,
            steps,
            on_disk,
            spent,
            task.environment,
            list(task.review_history),
        )

    def finish(
        self,
        task_description: str,
        repository_id: str,
        repository_path: str,
        source_files: list[GeneratedFile],
        steps: StepRecorder,
        on_disk: RunFiles,
        spent,
        created: list[str],
        review_history: list[ReviewHistory] | None = None,
        baseline: CompileResult | None = None,
        test_baseline: TestResult | None = None,
    ) -> Task:
        """Checks, review, tests: everything after the first draft.

        `baseline` is the type check from before the task
        wrote anything; errors already in it are not this
        task's. A revision has none: its own files are on
        disk, and their errors are exactly what it is for.
        """

        review_history = review_history or []

        # Rounds are numbered on from an earlier attempt's,
        # but the budget is this run's.
        earlier_reviews = len(review_history)

        review_iterations = earlier_reviews

        architecture_review: ArchitectureReview | None = None

        gates = Gates()

        rounds = 0

        fixes = 0

        # Two budgets, not one. The free checks get a few
        # fixes per round; the architect gets its rounds.
        # Sharing one counter let two compile errors use up
        # the rounds an architect's blockers needed, and the
        # blockers were never fixed. The loop only ends on
        # code the free checks have just passed -- or have
        # just failed, out of fixes -- so a review never
        # vouches for files changed after it.
        while True:

            rounds += 1

            self.write_files(
                repository_path,
                source_files,
                on_disk,
            )

            gates = self.gates(
                task_description,
                source_files,
                repository_path,
                baseline,
            )

            steps.record(
                "step.gates",
                f"#{rounds} · {gates.detail}",
                ok=gates.passed,
            )

            if not gates.passed:

                # A package nobody installed is no reason to
                # rewrite code: no rewrite makes it exist.
                # The run stops here and a human is offered
                # the install, instead of fixes being spent
                # on errors the developer cannot fix.
                needed = packages.missing(
                    [item.content for item in source_files],
                    repository_path,
                )

                if needed:
                    return self.needs_packages(
                        task_description,
                        repository_id,
                        repository_path,
                        source_files,
                        steps,
                        on_disk,
                        spent,
                        created,
                        gates,
                        rounds,
                        needed,
                        review_history,
                    )

                if fixes >= Settings.MAX_GATE_FIXES:
                    break

                fixes += 1

                source_files = self.developer.improve(
                    task_description,
                    source_files,
                    gates.brief(),
                    repository_path,
                )

                steps.record(
                    "step.improve",
                    describe_files(source_files),
                )

                continue

            architecture_review = self.architect.execute(
                task_description,
                source_files,
                review_history,
                repository_path,
            )

            review_iterations += 1

            steps.record(
                "step.architect",
                f"#{review_iterations} · "
                f"{architecture_review.score}/100 · "
                f"{architecture_review.recommendation.value}"
                f" · {len(architecture_review.blockers)}B",
                ok=not architecture_review.blockers,
            )

            review_history.append(
                self.history_entry(
                    review_iterations,
                    architecture_review,
                )
            )

            # Warnings and suggestions are recorded and
            # shipped; only blockers send the files back.
            if not architecture_review.blockers:
                break

            if architecture_review.recommendation == ReviewDecision.REJECT:
                break

            if (
                review_iterations - earlier_reviews
                >= Settings.MAX_REVIEW_LOOPS
            ):
                break

            # A fresh fix budget for the revised files.
            fixes = 0

            source_files = self.developer.improve(
                task_description,
                source_files,
                self.fix_brief(architecture_review),
                repository_path,
            )

            steps.record(
                "step.improve",
                describe_files(source_files),
            )

        if architecture_review is None:
            architecture_review = self.unreviewed(
                gates,
                rounds,
            )

        test_files = self.qa.execute(source_files)

        steps.record(
            "step.qa",
            describe_files(test_files),
        )

        generated_files = self.write_files(
            repository_path,
            source_files + test_files,
            on_disk,
        )

        steps.record(
            "step.written",
            f"{len(generated_files)}",
        )

        # Again now that the tests exist: a suite that does
        # not compile fails to load, and the runner then
        # reports nothing passing out of nothing -- which
        # reads like nothing happened rather than like the
        # code is broken.
        compile_result = type_checker.check(repository_path).since(baseline)

        steps.record(
            "step.types",
            f"{compile_result.status.value} · "
            f"{compile_result.summary}",
            ok=not compile_result.blocks_delivery,
        )

        test_result = self.run_tests(
            repository_path,
            compile_result,
            test_baseline,
        )

        if not compile_result.blocks_delivery:
            steps.record(
                "step.tests",
                f"{test_result.status.value} · "
                f"{test_result.summary}",
                ok=not test_result.blocks_delivery,
            )

        attempts = 0

        while (
            (
                compile_result.blocks_delivery
                or test_result.blocks_delivery
            )
            and attempts < Settings.MAX_TEST_LOOPS
        ):

            attempts += 1

            # The compiler names a file and a line, so when
            # it has something to say it is a better brief
            # than a failing assertion.
            failure = (
                compile_result.brief()
                if compile_result.blocks_delivery
                else TestExecutionAgent.fix_brief(
                    test_result,
                    source_files,
                    test_files,
                )
            )

            before = source_files

            source_files = self.developer.improve(
                task_description,
                source_files,
                failure,
                repository_path,
            )

            steps.record(
                "step.improve",
                describe_files(source_files),
            )

            # No second architecture review: a fix for a
            # failing test does not change the design, and
            # the structural checks below catch the one
            # thing it could break for free.
            stale = self.stale_suites(
                before,
                source_files,
                compile_result.output
                if compile_result.blocks_delivery
                else test_result.output,
            )

            refreshed = self.qa.execute(
                source_files,
                only=stale,
            )

            test_files = self.merge_suites(
                test_files,
                refreshed,
                source_files,
            )

            steps.record(
                "step.qa_refresh",
                f"#{attempts} · {len(refreshed)}/"
                f"{len(stale)} suite(s)",
            )

            generated_files = self.write_files(
                repository_path,
                source_files + test_files,
                on_disk,
            )

            gates = self.gates(
                task_description,
                source_files,
                repository_path,
                baseline,
            )

            compile_result = gates.compile_result

            steps.record(
                "step.types_retry",
                f"#{attempts} · {gates.detail} · "
                f"{compile_result.summary}",
                ok=gates.passed,
            )

            test_result = self.run_tests(
                repository_path,
                compile_result,
                test_baseline,
            )

            if not compile_result.blocks_delivery:
                steps.record(
                    "step.tests_retry",
                    f"#{attempts} · "
                    f"{test_result.status.value} · "
                    f"{test_result.summary}",
                    ok=not test_result.blocks_delivery,
                )

        # The structural findings are the last checked
        # ones, not the ones the architect saw: a fix after
        # the review can introduce a problem, and the
        # review would then vouch for files it never read.
        structural = gates.report.blockers

        recommendation = RecommendationPolicy.decide(
            architecture_review.blockers,
            structural,
            architecture_review.recommendation,
        )

        # Code that does not compile, or fails its tests,
        # is not approvable whatever the review said. The
        # gates are facts; the review is an opinion about
        # an earlier version of the files. Nor is code the
        # architect never saw, however clean it turned out.
        if recommendation == ReviewDecision.APPROVE and (
            compile_result.blocks_delivery
            or test_result.blocks_delivery
            or review_iterations == earlier_reviews
        ):
            recommendation = ReviewDecision.REQUEST_CHANGES

        calls = usage_ledger.since(spent)

        cost = usage_ledger.describe(calls)

        if cost:
            steps.record("step.usage", cost)

        # What a reviewer will be asked to approve. Read
        # only: the files are already on disk, so this
        # compares them with what git has recorded.
        diffs = GitDiffService.compare(
            repository_path,
            [item.path for item in generated_files],
        )

        return Task(
            repository_id=repository_id,
            repository_path=repository_path,
            description=task_description,
            architecture_review=architecture_review.review,
            architecture_score=architecture_review.score,
            recommendation=recommendation,
            blockers=architecture_review.blockers,
            warnings=architecture_review.warnings,
            suggestions=architecture_review.suggestions,
            structural=structural,
            review_iterations=review_iterations,
            review_history=review_history,
            generated_files=generated_files,
            test_result=test_result,
            compile_result=compile_result,
            diffs=diffs,
            environment=created,
            created_files=sorted(on_disk.created),
            steps=steps.steps,
            cost=usage_ledger.dollars(calls),
            status=TaskStatus.WAITING_FOR_APPROVAL,
        )

    @staticmethod
    def gates(
        task_description: str,
        source_files: list[GeneratedFile],
        repository_path: str,
        baseline: CompileResult | None = None,
    ) -> Gates:
        """The free checks, against what is on disk now."""

        return Gates(
            report=StructureValidator.validate(
                source_files,
                task_description,
                survey(repository_path),
            ),
            compile_result=type_checker.check(
                repository_path
            ).since(baseline),
        )

    @staticmethod
    def run_tests(
        repository_path: str,
        compile_result: CompileResult,
        baseline: TestResult | None = None,
    ) -> TestResult:

        if compile_result.blocks_delivery:
            return TestResult(
                status=TestStatus.NOT_RUN,
                output="Skipped: the code does not compile.",
            )

        return TestExecutionAgent.execute(repository_path).since(baseline)

    def needs_packages(
        self,
        task_description: str,
        repository_id: str,
        repository_path: str,
        source_files: list[GeneratedFile],
        steps: StepRecorder,
        on_disk: RunFiles,
        spent,
        created: list[str],
        gates: "Gates",
        rounds: int,
        needed: list[str],
        review_history: list[ReviewHistory],
    ) -> Task:
        """A task stopped before review, waiting for packages."""

        steps.record("step.packages", ", ".join(needed), ok=False)

        calls = usage_ledger.since(spent)

        cost = usage_ledger.describe(calls)

        if cost:
            steps.record("step.usage", cost)

        review = self.unreviewed(gates, rounds)

        return Task(
            repository_id=repository_id,
            repository_path=repository_path,
            description=task_description,
            architecture_review=review.review,
            architecture_score=0,
            recommendation=ReviewDecision.REQUEST_CHANGES,
            structural=gates.report.blockers,
            review_iterations=len(review_history),
            review_history=review_history,
            generated_files=source_files,
            compile_result=gates.compile_result,
            diffs=GitDiffService.compare(
                repository_path,
                [item.path for item in source_files],
            ),
            environment=created,
            created_files=sorted(on_disk.created),
            steps=steps.steps,
            cost=usage_ledger.dollars(calls),
            packages=needed,
            status=TaskStatus.WAITING_FOR_APPROVAL,
        )

    def recheck(self, task: Task) -> Task:
        """The task's own files through the checks again.

        After its packages are installed the code is the
        same and may now be right: it needs the compiler,
        the review, QA and the tests, not a rewrite.
        """

        spent = usage_ledger.mark()

        steps = StepRecorder()

        root = task.repository_path

        sources = [
            GeneratedFile(
                path=item.path,
                file_type=item.file_type,
                content=open(
                    FileWriter.resolve(root, item.path),
                    encoding="utf-8",
                ).read(),
            )
            for item in task.generated_files
            if item.file_type == FileType.SOURCE
        ]

        steps.record("step.recheck", describe_files(sources))

        return self.finish(
            task.description,
            task.repository_id,
            root,
            sources,
            steps,
            RunFiles(
                written={item.path for item in task.generated_files},
                created=set(task.created_files),
            ),
            spent,
            task.environment,
            list(task.review_history),
        )

    @staticmethod
    def unreviewed(
        gates: Gates,
        rounds: int,
    ) -> ArchitectureReview:
        """The review of a file set the free checks rejected.

        Written here rather than asked for: the architect
        would only have been told to repeat what the checks
        found, and it is the most expensive call in the
        run.
        """

        return ArchitectureReview(
            score=0,
            recommendation=ReviewDecision.REQUEST_CHANGES,
            review=(
                "Not reviewed. After "
                f"{rounds} round(s) the code still fails "
                "the structural checks or does not "
                "compile, so it never reached the "
                "architect.\n\n" + gates.brief()
            ),
            structural=gates.report.blockers,
            structure_report=gates.report,
        )

    @staticmethod
    def history_entry(
        iteration: int,
        review: ArchitectureReview,
    ) -> ReviewHistory:

        return ReviewHistory(
            iteration=iteration,
            score=review.score,
            recommendation=review.recommendation,
            review=review.review,
            resolved=review.resolved,
            blockers=review.blockers,
            warnings=review.warnings,
            suggestions=review.suggestions,
            structural=review.structural,
        )

    @staticmethod
    def stale_suites(
        before: list[GeneratedFile],
        after: list[GeneratedFile],
        output: str,
    ) -> set[str]:
        """Source files whose suite has to be written again.

        Those that changed, and those whose suite the
        failure names: a wrong test fails against correct
        code, and leaving it alone would fail the same way
        next time.

        `output` is the compiler's or the runner's own
        output, not the brief built from it: the brief
        lists every file in the task, and reading paths
        out of it named every suite as failing.
        """

        stale = changed_paths(before, after)

        named = set(FileParser.paths_in(output))

        for item in after:

            if (
                item.path in named
                or QAAgent.test_path(item.path) in named
            ):
                stale.add(item.path)

        return stale

    @staticmethod
    def merge_suites(
        current: list[GeneratedFile],
        refreshed: list[GeneratedFile],
        source_files: list[GeneratedFile],
    ) -> list[GeneratedFile]:
        """The old suites, with the rewritten ones swapped in.

        A suite whose source file is gone goes with it.
        """

        wanted = {
            QAAgent.test_path(item.path)
            for item in source_files
        }

        merged = {
            item.path: item
            for item in current
            if item.path in wanted
        }

        for item in refreshed:
            merged[item.path] = item

        return list(merged.values())

    @staticmethod
    def prepare(repository_path: str) -> list[str]:
        """Scaffolding, before a single task is written.

        Deterministic on purpose. The alternative was a
        planned task per config file, and one of those
        took twenty-three minutes of model time to produce
        a package.json.
        """

        if not Settings.AUTO_BOOTSTRAP:
            return []

        created = bootstrap(
            repository_path,
            describe(repository_path),
        )

        if created:
            print(
                "BOOTSTRAP: created "
                + ", ".join(created)
            )

        return created

    @staticmethod
    def fix_brief(review: ArchitectureReview) -> str:
        """What the developer has to act on after a review."""

        return review.review

    def write_files(
        self,
        repository_path: str,
        files: list[GeneratedFile],
        on_disk: RunFiles | None = None,
    ) -> list[GeneratedFile]:
        """Writes the run's files into the repository.

        Nothing is written when no repository folder was
        given, so the workflow still runs standalone. A
        file whose path is unsafe is skipped rather than
        failing the whole run.
        """

        if not repository_path:
            return files

        on_disk = on_disk if on_disk is not None else RunFiles()

        written: list[GeneratedFile] = []

        for item in files:

            try:
                target = FileWriter.resolve(
                    repository_path,
                    item.path,
                )

                if (
                    item.path not in on_disk.written
                    and not os.path.exists(target)
                ):
                    on_disk.created.add(item.path)

                written.append(
                    FileWriter.write(
                        repository_path,
                        FileGenerationResult(
                            relative_path=item.path,
                            content=item.content,
                            file_type=item.file_type,
                        ),
                    )
                )

            except ValueError as error:
                print(f"SKIPPED {item.path}: {error}")

        if not written:
            raise RuntimeError(
                "No generated file could be written to "
                f"{repository_path}."
            )

        current = {item.path for item in files}

        self.remove_dropped(
            repository_path,
            on_disk,
            current,
        )

        on_disk.written |= current

        return written

    @staticmethod
    def remove_dropped(
        repository_path: str,
        on_disk: RunFiles,
        current: set[str],
    ) -> None:
        """Deletes files this run created and has since dropped.

        Every write is the run's whole file set: sources
        alone before QA has written anything, sources and
        suites after. So a path missing from a write is a
        path the run no longer has.
        """

        for path in sorted(on_disk.written - current):

            if path not in on_disk.created:
                continue

            try:
                os.remove(
                    FileWriter.resolve(repository_path, path)
                )

                print(f"REMOVED {path}: dropped by this run")

            except (OSError, ValueError) as error:
                print(f"could not remove {path}: {error}")

            on_disk.written.discard(path)

            on_disk.created.discard(path)
