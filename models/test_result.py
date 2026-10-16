import re
from dataclasses import dataclass, replace
from enum import Enum

# Vitest's line for each failing test: " FAIL  tests/days.test.ts > days > adds".
FAIL_LINE = re.compile(r"^\s*FAIL\s+(\S+\.(?:test|spec)\.[cm]?[jt]sx?.*?)\s*$", re.MULTILINE)


class TestStatus(str, Enum):
    NOT_RUN = "NOT_RUN"

    PASSED = "PASSED"

    FAILED = "FAILED"

    # The suite ran but blew up: a compile error, an
    # import that does not resolve, a crash.
    ERROR = "ERROR"

    # Nothing to run with: no node, no vitest, no project.
    # Not the generated code's fault.
    UNAVAILABLE = "UNAVAILABLE"

    @classmethod
    def parse(
        cls,
        value: str,
    ) -> "TestStatus":

        try:
            return cls(str(value).upper())

        except ValueError:
            return cls.NOT_RUN


@dataclass
class TestResult:
    """What happened when the generated tests were run."""

    status: TestStatus = TestStatus.NOT_RUN

    total_tests: int = 0

    failed_tests: int = 0

    duration_seconds: float = 0.0

    output: str = ""

    executed_at: str = ""

    @property
    def passed(self) -> bool:

        return self.status == TestStatus.PASSED

    @property
    def passed_tests(self) -> int:

        return max(0, self.total_tests - self.failed_tests)

    @property
    def blocks_delivery(self) -> bool:
        """Whether this result should send work back.

        Only a real failure does. A missing toolchain is an
        environment problem, and sending the developer
        round again cannot fix it.
        """

        return self.status in (
            TestStatus.FAILED,
            TestStatus.ERROR,
        )

    def failing(self) -> set[str]:
        """The failing tests, by file and full name, as Vitest lists them."""

        return {match.strip() for match in FAIL_LINE.findall(self.output)}

    def since(self, baseline: "TestResult | None") -> "TestResult":
        """Judged only on the tests that started failing.

        Vitest runs every suite in the project, so a test an
        earlier task left failing failed every task after it,
        and each paid the developer to fix a file it had not
        written. Tests already failing before this task are
        set aside: none newly failing is a pass; otherwise
        the output leads with the new failures alone.
        """

        if (
            baseline is None
            or not self.blocks_delivery
            or not baseline.blocks_delivery
        ):
            return self

        now = self.failing()

        before = baseline.failing()

        earlier = now & before

        if not now or not earlier:
            return self

        new = sorted(now - before)

        note = (
            f"{len(earlier)} failing test(s) were failing before this task, "
            "and are not its to fix:\n"
            + "\n".join(f"- {name}" for name in sorted(earlier))
        )

        if not new:
            return replace(
                self,
                status=TestStatus.PASSED,
                output=f"No test newly fails. {note}\n\n{self.output}",
            )

        return replace(
            self,
            output=(
                "Failing since this task -- fix these:\n"
                + "\n".join(f"- {name}" for name in new)
                + f"\n\n{note}\n\n{self.output}"
            ),
        )

    @property
    def summary(self) -> str:

        if self.status == TestStatus.UNAVAILABLE:
            return "Tests were not run"

        if self.status == TestStatus.PASSED and self.failed_tests:
            return (
                f"{self.passed_tests}/{self.total_tests} passed; "
                f"the {self.failed_tests} failing were failing before this task"
            )

        if self.status == TestStatus.NOT_RUN:
            return "Not run"

        return (
            f"{self.passed_tests}/{self.total_tests} passed"
            f" in {self.duration_seconds:.1f}s"
        )
