import os
import posixpath
import re

from config.settings import Settings
from models.file_type import FileType
from models.generated_file import GeneratedFile
from services.code_cleaner import strip_code_fences, strip_leading_prose
from services.parallel import run_all
from services.file_bundle import FileBundle
from services.file_parser import FileParseError, FileParser
from services.llm_factory import LLMFactory
from services.repository_survey import is_test_path, survey
from services.structure_validator import StructureValidator

# The same trap as in the developer: a small model answers
# with the path it was shown, so the path it is shown is
# one no real project would have, and it is dropped if it
# comes back anyway.
EXAMPLE_TEST_PATH = "tests/example-one.test.ts"

# Files there is nothing to assert about: a config file, a
# barrel, a file of nothing but types. Writing a suite for
# one costs a call and produces a test that asserts the
# language works.
NOT_WORTH_TESTING = (
    ".d.ts",
    ".json",
    "index.ts",
)

# A suite imports what it tests, so only code can have one.
# datepicker's demo/index.html got a suite importing
# "../demo/index", which does not exist, and the task
# stopped on a compile error in a file nobody needed.
TESTABLE = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")

# A tool's config: vite.config.ts, eslint.config.js.
CONFIG_FILE = re.compile(r"(^|/)[^/]*\.config\.[cm]?[jt]sx?$")

# How much of the imported files a suite's prompt may carry.
MAX_IMPORTED_CHARS = 12_000

# Code that touches the DOM. Vitest runs in Node, where none
# of these exist: the suite has to ask for jsdom.
USES_DOM = re.compile(
    r"\b(?:document|window)\.[A-Za-z_$]|\bHTML\w*Element\b|\b(?:Keyboard|Mouse|Focus|Pointer)Event\b"
)

# Comments are prose: "statistics for a CSV document." is
# not the DOM (csv-kit #7).
COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)

DOM_DIRECTIVE = "// @vitest-environment jsdom"

# A barrel's line: "export type { CalendarDate, Clock } from './types.js'".
RE_EXPORT = re.compile(r"""\bexport\s*(?:type\s*)?\{([^}]*)\}\s*from\s*['"]([^'"]+)['"]""")


DOM_RULE = f"""- the file under test uses the DOM, and Vitest runs in
  Node: the suite's very first line is
  {DOM_DIRECTIVE}
  and it uses the real document, never a fake one
"""


def uses_dom(content: str) -> bool:
    """Whether code reaches for the DOM's globals."""

    return bool(USES_DOM.search(COMMENT.sub("", content)))


def with_dom(suite: str) -> str:
    """The suite, asking for jsdom on its first line if it did not."""

    if "@vitest-environment" in suite:
        return suite

    return f"{DOM_DIRECTIVE}\n{suite}"


def notes_rule(notes: str) -> str:
    """A human's revision notes, as a rule the suite obeys."""

    if not notes.strip():
        return ""

    return f"""- a human reviewed this task and wrote the notes
  below. Where they say what a test should check or
  expect, they are right and your own reading is not:

{notes.strip()}

"""


def existing_rule(existing: str) -> str:
    """The suite already on disk, to extend rather than replace."""

    if not existing.strip():
        return "- at most 3 tests\n"

    return f"""- this suite already exists, from earlier work:

{existing.rstrip()}

  return the whole suite: keep every test in it that
  still holds for the file as it is now, fix the ones
  it no longer matches, and add at most 3 new tests
  for what is new
"""


class QAAgent:
    def __init__(
        self,
    ) -> None:
        self.llm = LLMFactory.create("qa")

        self.notes = ""

    def execute(
        self,
        files: list[GeneratedFile],
        only: set[str] | None = None,
        repository_path: str = "",
        notes: str = "",
    ) -> list[GeneratedFile]:
        """Suites for the source files, or for `only` those.

        `notes` are a human's revision notes. They reached
        only the developer, so a wrong test could not be
        corrected through a revision (csv-kit #5: a test
        expected Date.UTC(5, ...) to be the year 5).

        `only` names the source paths that need a suite
        again -- after a fix, the files that changed. The
        rest of the project is still listed, so a suite can
        import from it; it just is not rewritten. Writing
        every suite again after a one-file fix paid for a
        dozen calls to reproduce what was already there.
        """

        # Read by _imported: what this task wrote, and where.
        self.repository_path = repository_path

        self.notes = notes

        self.files = files

        if Settings.GENERATE_FILE_BY_FILE:

            written = self._suite_per_file(files, only)

            # A refresh keeps the suites it could not
            # rewrite. Falling back to one call for the
            # whole project would rewrite all of them.
            if written or only is not None:
                return written

        return self._all_at_once(files)

    # ------------------------------------------------
    # a suite per source file
    # ------------------------------------------------

    @staticmethod
    def worth_testing(
        files: list[GeneratedFile],
    ) -> list[GeneratedFile]:

        return [
            item
            for item in files
            if item.path.endswith(TESTABLE)
            and not item.path.endswith(NOT_WORTH_TESTING)
            and not CONFIG_FILE.search(item.path)
            and not is_test_path(item.path)
            and item.content.strip()
        ]

    @staticmethod
    def import_specifier(
        test_path: str,
        source_path: str,
    ) -> str:
        """What the suite must import, spelled out.

        The relative path between two known paths is
        arithmetic, and the prompt used to ask for it.
        A 3B model answered './clock' for a suite in
        tests/ importing src/clock.ts, and every generated
        suite failed to resolve -- eight of them in one
        run, found the first time the test gate could
        actually run.
        """

        target = posixpath.splitext(source_path)[0]

        specifier = posixpath.relpath(
            target,
            posixpath.dirname(test_path) or ".",
        ).replace("\\", "/")

        return (
            specifier
            if specifier.startswith(".")
            else f"./{specifier}"
        )

    @staticmethod
    def test_path(source_path: str) -> str:
        """tests/<name>.test.ts for src/<anything>/<name>.ts."""

        name = source_path.rsplit("/", 1)[-1]

        for suffix in (".tsx", ".ts", ".mts", ".js"):
            name = name.removesuffix(suffix)

        return f"tests/{name}.test.ts"

    def _suite_per_file(
        self,
        files: list[GeneratedFile],
        only: set[str] | None = None,
    ) -> list[GeneratedFile]:
        """One call per source file.

        The same reason the developer writes a file at a
        time: one answer covering eight files is one
        answer's worth of attention split eight ways, and
        what came back was a single suite for the whole
        project.
        """

        targets = [
            item
            for item in self.worth_testing(files)
            if only is None or item.path in only
        ]

        if not targets:
            return []

        listing = FileBundle.structure(files)

        def suite(numbered: tuple[int, GeneratedFile]) -> GeneratedFile | None:

            position, source = numbered

            path = self.test_path(source.path)

            print(
                f"QA: writing {path} "
                f"({position}/{len(targets)})"
            )

            content = self._suite_for(
                source,
                listing,
                path,
            )

            if not content:
                return None

            return GeneratedFile(
                path=path,
                file_type=FileType.TEST,
                content=content,
            )

        tests = [
            item
            for item in run_all(list(enumerate(targets, start=1)), suite)
            if item is not None
        ]

        self._announce(tests)

        return tests

    def _imported(self, source: GeneratedFile) -> str:
        """The files the source imports, as they are, for the prompt.

        Shown only the file under test, QA guessed what its
        types are: datepicker's CalendarDate is a branded
        string, and twice the suites built it as an object.
        The developer is shown what it imports; so is QA now.
        """

        written = {item.path: item.content for item in getattr(self, "files", [])}

        found = survey(getattr(self, "repository_path", ""))

        known = set(found.files) | set(written)

        blocks: list[str] = []

        shown: set[str] = {source.path}

        spent = 0

        def show(path: str) -> str:
            """Adds a file to the prompt once, within the budget; its content."""

            nonlocal spent

            content = written.get(path) or found.read(path)

            if not content or path in shown or spent + len(content) > MAX_IMPORTED_CHARS:
                return content or ""

            shown.add(path)

            spent += len(content)

            blocks.append(f"// {path}\n{content.strip()}")

            return content

        for target, names in StructureValidator.imports(source.content):

            path = StructureValidator.resolve(source.path, target, known)

            if not path or path == source.path:
                continue

            content = show(path)

            # A barrel only names where things live. Shown
            # src/index.ts alone, QA still did not know what
            # CalendarDate was: the file that defines each
            # imported name is shown too.
            wanted = set(names or ())

            for listed, origin in RE_EXPORT.findall(content):

                exported = {
                    raw.strip().split(" as ")[-1].strip().removeprefix("type ").strip()
                    for raw in listed.split(",")
                }

                if wanted & exported:

                    defining = StructureValidator.resolve(path, origin, known)

                    if defining:
                        show(defining)

        if not blocks:
            return ""

        return (
            "\nIt imports these files. Build test data from their types "
            "exactly as defined here -- do not guess a type's shape:\n\n"
            + "\n\n".join(blocks)
            + "\n"
        )

    def _suite_for(
        self,
        source: GeneratedFile,
        listing: str,
        path: str,
    ) -> str:
        """One source file's suite, or '' if the call failed."""

        specifier = self.import_specifier(
            path,
            source.path,
        )

        # Written again from nothing, a suite kept 3 tests and
        # lost the rest (csv-kit: parser.test.ts lost its RFC
        # 4180 edge cases to a task that touched the parser).
        existing = ""

        root = getattr(self, "repository_path", "")

        on_disk = os.path.join(root or "", path)

        if root and os.path.isfile(on_disk):
            with open(on_disk, encoding="utf-8", errors="replace") as handle:
                existing = handle.read()

        prompt = f"""
You are a QA Engineer.

The project has these files:
{listing}

Write a Vitest suite for exactly one of them:
{source.path}

That file:

{source.content}
{self._imported(source)}
Rules:

- the suite goes in {path}
- begin with exactly these two imports, and
  do not change the path in the second:

    import {{ describe, it, expect }} from 'vitest';
    import {{ ... }} from '{specifier}';

{existing_rule(existing)}{DOM_RULE if uses_dom(source.content) else ""}{notes_rule(self.notes)}- use describe, it and expect
- this is Vitest, not Jest. For a mock write
  vi.fn(), and for a mocked type use
  ReturnType<typeof vi.fn>. The name `jest` does
  not exist here and a suite using it fails to
  run at all
- test what this file does, not what it imports
- do not invent exports it does not have

Return the TypeScript only: no JSON, no markdown
fence, no explanation.
"""

        try:
            answer = self.llm.generate_text(prompt)

        except Exception as error:  # noqa: BLE001

            # One missing suite is recoverable; the test
            # gate runs whatever was written.
            print(f"QA: {path} failed ({error})")

            return ""

        suite = strip_leading_prose(strip_code_fences(answer))

        return with_dom(suite) if suite and uses_dom(source.content) else suite

    # ------------------------------------------------
    # when a suite fails: the test, or the code?
    # ------------------------------------------------

    def judge(
        self,
        task: str,
        sources: list[GeneratedFile],
        suites: list[GeneratedFile],
        output: str,
    ) -> tuple[str, str]:
        """("TEST" or "CODE", why) for a failing run; ("", "") if unsure.

        A failing test sent the developer to change the
        code, also when the test's expectation was what was
        wrong (csv-kit #7: an empty-value count worked out
        wrongly by hand) -- paying to break correct code.
        """

        prompt = f"""
You are a QA Engineer. A Vitest suite you wrote fails
against the code below. Decide which one is wrong.

The task:

{task}

The code:

{FileBundle.render(sources)}

The suites:

{FileBundle.render(suites)}

The test run:

{output}

Work the failing case out by hand, from the task and
the input the test gives, value by value. Then answer
with exactly one word on the first line -- TEST if the
test's expectation is wrong and the code is right, CODE
if the code is wrong -- and one sentence on the second
line saying which value is wrong and what it should be.
"""

        try:
            answer = self.llm.generate_text(prompt)

        except Exception as error:  # noqa: BLE001 -- unsure is an answer

            print(f"QA: judging failed ({error})")

            return "", ""

        lines = [line.strip() for line in strip_code_fences(answer).splitlines() if line.strip()]

        if not lines:
            return "", ""

        verdict = lines[0].strip(" .:*").upper()

        if verdict not in ("TEST", "CODE"):
            return "", ""

        return verdict, " ".join(lines[1:2])

    # ------------------------------------------------
    # one call for everything
    # ------------------------------------------------

    def _all_at_once(
        self,
        files: list[GeneratedFile],
    ) -> list[GeneratedFile]:

        prompt = f"""
You are a QA Engineer.

Write a Vitest suite for this project.

Source files:

{FileBundle.structure(files)}

Code:

{FileBundle.render(files)}

Rules:

- one test file per source file worth testing
- a test file for src/x/y.ts goes in tests/y.test.ts
- at most 3 tests per file
{notes_rule(self.notes)}- use describe, it and expect
- this is Vitest, not Jest: mocks are vi.fn()
- import from the matching source file

Return only JSON in exactly this shape:

{{
  "files": [
    {{
      "path": "tests/example-one.test.ts",
      "content": "...typescript..."
    }}
  ]
}}

That path shows the format only; never use it.
Escape newlines in "content" as \n.
No explanations outside the JSON.
"""

        raw = self.llm.generate_text(prompt)

        try:
            tests = FileParser.parse(
                raw,
                FileType.TEST,
            )

        except (FileParseError, ValueError) as error:
            tests = self._single_file(raw, files, error)

        tests = [
            item
            for item in tests
            if item.path != EXAMPLE_TEST_PATH
        ]

        self._announce(tests)

        return tests

    @staticmethod
    def _announce(tests: list[GeneratedFile]) -> None:

        print("=" * 80)
        print(f"QA RESULT ({len(tests)} file(s))")
        print("=" * 80)
        print(FileBundle.structure(tests))
        print("=" * 80)

    @staticmethod
    def _single_file(
        raw: str,
        files: list[GeneratedFile],
        error: Exception,
    ) -> list[GeneratedFile]:
        """Falls back to one suite when the JSON is unusable."""

        content = strip_code_fences(raw)

        if not content.strip():
            print(f"QA: no usable tests ({error})")

            return []

        stem = "generated"

        if files:
            stem = files[0].path.rsplit("/", 1)[-1]
            stem = stem.removesuffix(".ts")

        print(
            f"QA: JSON unusable ({error}); "
            "falling back to a single suite"
        )

        return [
            GeneratedFile(
                path=f"tests/{stem}.test.ts",
                file_type=FileType.TEST,
                content=content,
            )
        ]
