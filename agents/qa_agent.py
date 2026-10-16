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

# How much of the imported files a suite's prompt may carry.
MAX_IMPORTED_CHARS = 12_000

# Code that touches the DOM. Vitest runs in Node, where none
# of these exist: the suite has to ask for jsdom.
USES_DOM = re.compile(
    r"\bdocument\.|\bwindow\.|\bHTML\w*Element\b|\b(?:Keyboard|Mouse|Focus|Pointer)Event\b"
)

DOM_DIRECTIVE = "// @vitest-environment jsdom"


DOM_RULE = f"""- the file under test uses the DOM, and Vitest runs in
  Node: the suite's very first line is
  {DOM_DIRECTIVE}
  and it uses the real document, never a fake one
"""


def uses_dom(content: str) -> bool:
    """Whether code reaches for the DOM's globals."""

    return bool(USES_DOM.search(content))


def with_dom(suite: str) -> str:
    """The suite, asking for jsdom on its first line if it did not."""

    if "@vitest-environment" in suite:
        return suite

    return f"{DOM_DIRECTIVE}\n{suite}"


class QAAgent:
    def __init__(
        self,
    ) -> None:
        self.llm = LLMFactory.create("qa")

    def execute(
        self,
        files: list[GeneratedFile],
        only: set[str] | None = None,
        repository_path: str = "",
    ) -> list[GeneratedFile]:
        """Suites for the source files, or for `only` those.

        `only` names the source paths that need a suite
        again -- after a fix, the files that changed. The
        rest of the project is still listed, so a suite can
        import from it; it just is not rewritten. Writing
        every suite again after a one-file fix paid for a
        dozen calls to reproduce what was already there.
        """

        # Read by _imported: what this task wrote, and where.
        self.repository_path = repository_path

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
            if not item.path.endswith(NOT_WORTH_TESTING)
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

        spent = 0

        for target, _ in StructureValidator.imports(source.content):

            path = StructureValidator.resolve(source.path, target, known)

            if not path or path == source.path:
                continue

            content = written.get(path) or found.read(path)

            if not content or spent + len(content) > MAX_IMPORTED_CHARS:
                continue

            spent += len(content)

            blocks.append(f"// {path}\n{content.strip()}")

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

- at most 3 tests
{DOM_RULE if uses_dom(source.content) else ""}- use describe, it and expect
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
- use describe, it and expect
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
