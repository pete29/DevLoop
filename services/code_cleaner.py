import re

THINK_BLOCK_PATTERN = re.compile(
    r"<think>.*?</think>",
    re.DOTALL,
)

FENCE_PATTERN = re.compile(
    r"^```[a-zA-Z0-9+#-]*\s*\n?|\n?```\s*$",
    re.MULTILINE,
)

# How a TypeScript file can begin. An import has to be a
# whole statement: "import { x } from './y' is not
# allowed, so..." is a sentence about one.
CODE_START = re.compile(
    r"""^(?:
        import\s[^'"]*\bfrom\s*(['"])[^'"]+\1\s*;?\s*$
      | import\s*(['"])[^'"]+\2\s*;?\s*$
      | import\s+(?:type\s+)?\{[^}]*$
      | (?://|/\*|\*|@|['"]use\s)
      | (?:export|const|let|var|function|class|abstract|type|interface|enum|declare|namespace|async)\b
      | (?:describe|it|test|vi|beforeEach|afterEach|beforeAll|afterAll|expect)\b
    )""",
    re.VERBOSE,
)


def strip_thinking(
    text: str,
) -> str:
    """Remove inline <think> blocks emitted by reasoning models."""

    return THINK_BLOCK_PATTERN.sub(
        "",
        text,
    ).strip()


def strip_leading_prose(
    text: str,
) -> str:
    """Drops sentences a model wrote above the code.

    Asked for code only, a model still sometimes explains
    itself on the first line, and one such line fails the
    type check of every task after it.
    """

    lines = text.strip().split("\n")

    while lines and not CODE_START.match(lines[0].strip()):
        lines.pop(0)

    return "\n".join(lines).strip()


def strip_code_fences(
    text: str,
) -> str:
    """Remove markdown code fences so only raw code is left."""

    return FENCE_PATTERN.sub(
        "",
        text.strip(),
    ).strip()
