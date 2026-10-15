"""Offline checks that agents see the code a task builds on.

Real files in a temp folder, a fake model that records the
prompts it is sent:

    python -m tests.context_files_test

From a real run: a task "accept a list of PasswordRule"
was written knowing only that src/password-rule.ts exports
PasswordRule. The developer guessed ten method names and
called whichever existed; it compiled, its tests passed,
and the architect rightly blocked it.
"""

import os
import shutil
import tempfile

import services.llm_factory as factory
from models.file_type import FileType
from models.generated_file import GeneratedFile
from services.repository_survey import is_test_path, survey

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


class Recorder:
    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts: list[str] = []

    def generate_text(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.answers.pop(0) if self.answers else ""


RULE = """export interface PasswordRule {
  check(password: string): string | null;
}
"""


def write(root: str, relative: str, content: str) -> None:

    full = os.path.join(root, *relative.split("/"))

    os.makedirs(os.path.dirname(full), exist_ok=True)

    with open(full, "w", encoding="utf-8") as handle:
        handle.write(content)


root = tempfile.mkdtemp()

try:

    write(root, "src/password-rule.ts", RULE)
    write(root, "src/min-length.rule.ts", "export class MinLengthRule {}\n")
    write(root, "src/big.ts", "export const Huge = 1;\n" + "// x\n" * 4000)
    write(root, "tests/password-rule.test.ts", "export const PasswordRuleSpec = 1;\n")

    found = survey(root)

    print("=" * 80)
    print("THE FILES A TASK NAMES COME WITH THEIR CONTENT")
    print("=" * 80)

    task = "Create PasswordValidator. It accepts a list of PasswordRule."

    check(
        "the file exporting a named symbol is picked",
        [path for path, _ in found.referenced(task)],
        ["src/password-rule.ts"],
    )

    check(
        "in full",
        found.referenced(task)[0][1],
        RULE,
    )

    check(
        "whole words only: PasswordRules names nothing",
        found.referenced("a list of PasswordRules"),
        [],
    )

    check(
        "a file can be excluded",
        found.referenced(task, {"src/password-rule.ts"}),
        [],
    )

    check(
        "a file over the budget is left out",
        found.referenced("Huge PasswordRule", budget=2000),
        [("src/password-rule.ts", RULE)],
    )

    check(
        "test suites are never offered as context",
        found.referenced("PasswordRuleSpec"),
        [],
    )

    print()
    print("=" * 80)
    print("THE DEVELOPER IS SHOWN THEM")
    print("=" * 80)

    llm = Recorder(
        [
            '{"files": [{"path": "src/password-validator.ts", '
            '"content": "Validates against the rules."}, '
            '{"path": "tests/password-validator.test.ts", '
            '"content": "Its tests."}]}',
            "export class PasswordValidator {}",
        ]
    )

    original = factory.LLMFactory.create

    factory.LLMFactory.create = classmethod(lambda cls, role="": llm)

    try:
        from agents.developer_agent import DeveloperAgent

        files = DeveloperAgent().execute(task, root)

    finally:
        factory.LLMFactory.create = original

    check(
        "the planning call carries the interface",
        "check(password: string): string | null;" in llm.prompts[0],
        True,
    )

    check(
        "and so does the call that writes the file",
        "check(password: string): string | null;" in llm.prompts[1],
        True,
    )

    check(
        "a test file in the developer's plan is dropped",
        [item.path for item in files],
        ["src/password-validator.ts"],
    )

    check(
        "so only one file was written",
        len(llm.prompts),
        2,
    )

    print()
    print("=" * 80)
    print("TESTS ARE QA'S")
    print("=" * 80)

    for path, expected in (
        ("tests/a.test.ts", True),
        ("src/a.test.ts", True),
        ("src/a.spec.ts", True),
        ("src/__tests__/a.ts", True),
        ("src/a.ts", False),
        ("src/testing-utils.ts", False),
    ):
        check(f"{path} is a test: {expected}", is_test_path(path), expected)

    from agents.qa_agent import QAAgent

    check(
        "QA does not write a suite for a suite",
        [
            item.path
            for item in QAAgent.worth_testing(
                [
                    GeneratedFile(
                        "src/a.ts", FileType.SOURCE, "export const a = 1;"
                    ),
                    GeneratedFile(
                        "tests/a.test.ts",
                        FileType.SOURCE,
                        "it('a', () => {});",
                    ),
                ]
            )
        ],
        ["src/a.ts"],
    )

finally:
    shutil.rmtree(root, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL CONTEXT FILE CHECKS PASSED")
print("=" * 80)
