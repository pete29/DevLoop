from dataclasses import dataclass, field
from enum import Enum


class CompileStatus(str, Enum):
    NOT_RUN = "NOT_RUN"

    PASSED = "PASSED"

    FAILED = "FAILED"

    # The compiler is not installed, or there is no
    # tsconfig to compile against.
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class CompileError:
    """One thing the compiler refused, where it refused it."""

    path: str = ""

    line: int = 0

    code: str = ""

    message: str = ""

    def __str__(self) -> str:

        where = (
            f"{self.path}:{self.line}"
            if self.path
            else "the project"
        )

        return f"{where} — {self.message}"


@dataclass
class CompileResult:
    """Whether the generated code compiles at all.

    Separate from the test gate because it answers a
    different question. A file that does not parse makes
    every suite in the repository fail to load, and the
    runner then reports zero tests passing out of zero --
    which reads like nothing happened rather than like the
    code is broken.
    """

    status: CompileStatus = CompileStatus.NOT_RUN

    errors: list[CompileError] = field(default_factory=list)

    output: str = ""

    reason: str = ""

    duration_seconds: float = 0.0

    @property
    def blocks_delivery(self) -> bool:
        """Only a real failure sends the work back.

        A missing compiler is not the developer's fault and
        cannot be fixed by rewriting the code, so it is
        reported and stepped over -- the same split the
        test gate makes between FAILED and UNAVAILABLE.
        """

        return self.status == CompileStatus.FAILED

    def since(self, baseline: "CompileResult | None") -> "CompileResult":
        """Only the errors that were not there before.

        A task is judged on what it broke. An error left by
        an earlier task -- a suite that does not parse, say
        -- failed every task after it, and each one paid the
        developer to fix a file it had not written. Errors
        match on file, code and message, not line: an edit
        above an old error moves it without fixing it.
        """

        if (
            baseline is None
            or self.status != CompileStatus.FAILED
            or baseline.status != CompileStatus.FAILED
        ):
            return self

        known = {
            (error.path, error.code, error.message)
            for error in baseline.errors
        }

        new = [
            error
            for error in self.errors
            if (error.path, error.code, error.message) not in known
        ]

        earlier = len(self.errors) - len(new)

        if not earlier:
            return self

        return CompileResult(
            status=CompileStatus.FAILED if new else CompileStatus.PASSED,
            errors=new,
            output=self.output,
            reason=f"{earlier} error(s) were there before this task",
            duration_seconds=self.duration_seconds,
        )

    @property
    def summary(self) -> str:

        if self.status == CompileStatus.PASSED:
            return "no new type errors · " + self.reason if self.reason else "no type errors"

        if self.status == CompileStatus.FAILED and self.reason:
            return f"{len(self.errors)} new type error(s) · {self.reason}"

        if self.status == CompileStatus.FAILED:
            return f"{len(self.errors)} type error(s)"

        return self.reason or self.status.value

    def brief(self) -> str:
        """What the developer is told to fix.

        Each error names a file and a line, which is the
        whole point: the compiler knows exactly where the
        problem is, so nobody has to ask the model to
        guess.
        """

        if not self.errors:
            return self.output

        lines = [
            (
                "The TypeScript compiler rejected this "
                "code. Fix exactly these, and change "
                "nothing else:"
            )
        ]

        for error in self.errors[:20]:
            lines.append(f"- {error}")

        if len(self.errors) > 20:
            lines.append(
                f"- ... and {len(self.errors) - 20} more"
            )

        return "\n".join(lines)
