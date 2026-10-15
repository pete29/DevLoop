"""Offline checks for prompt caching.

A cache hit needs the cached blocks to be the same bytes
in every call that should share them, so that is what this
pins down. No model is called:

    python -m tests.prompt_cache_test
"""

import json
import os
import shutil
import tempfile

import services.llm_factory as factory
from config.settings import Settings
from models.file_type import FileType
from models.generated_file import GeneratedFile
from services.prompt_cache import ask

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


PLAN = {
    "files": [
        {"path": "src/blocklist-rule.ts", "content": "The rule."},
        {"path": "src/common-passwords.ts", "content": "The list."},
    ]
}


class Caching:
    """A provider that caches: records every call's blocks."""

    def __init__(self):
        self.calls: list[tuple[list[str], str]] = []

    def generate_text(self, prompt):
        raise AssertionError("a caching provider gets generate_cached")

    def generate_cached(self, cached, prompt):

        self.calls.append((list(cached), prompt))

        if "no code at this stage" in prompt:
            return json.dumps(PLAN)

        if "SCORE" in "".join(cached):
            return "SCORE: 90\nRECOMMENDATION: APPROVE\nBLOCKERS:\n- None\n"

        return "export const x = 1;\n"


class Plain:
    def __init__(self):
        self.prompts: list[str] = []

    def generate_text(self, prompt):
        self.prompts.append(prompt)
        return "ok"


print("=" * 80)
print("ASK SENDS THE SAME TEXT EITHER WAY")
print("=" * 80)

plain = Plain()

ask(plain, ["A", "", "B"], "C")

check("a provider that cannot cache gets one string", plain.prompts, ["ABC"])

caching = Caching()

ask(caching, ["A", "  ", "B"], "C")

check("one that can gets the blocks, empty ones dropped", caching.calls, [(["A", "B"], "C")])

print()
print("=" * 80)
print("THE CLAUDE CALL MARKS EACH CACHED BLOCK")
print("=" * 80)

from services import claude_service  # noqa: E402


class FakeStream:
    def __init__(self, sent):
        self.sent = sent

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):

        class Usage:
            input_tokens = 10
            output_tokens = 5
            cache_read_input_tokens = 700
            cache_creation_input_tokens = 0

        class Block:
            type = "text"
            text = "done"

        class Message:
            model = "claude-opus-5-5"
            usage = Usage()
            content = [Block()]
            stop_reason = "end_turn"
            stop_details = None

        return Message()


class FakeClient:
    def __init__(self):
        self.sent = []

        class Messages:
            def stream(inner, **kwargs):
                self.sent.append(kwargs)
                return FakeStream(kwargs)

        class Beta:
            messages = Messages()

        self.beta = Beta()


service = claude_service.ClaudeService.__new__(claude_service.ClaudeService)
service.client = FakeClient()
service.model = "claude-opus-5-5"
service.effort = "high"
service.role = "architect"

service.generate_cached(["rules", "context"], "the task")

content = service.client.sent[-1]["messages"][0]["content"]

check(
    "every cached block carries a breakpoint, the variable part none",
    [(block["text"], "cache_control" in block) for block in content],
    [("rules", True), ("context", True), ("the task", False)],
)

service.generate_cached(["1", "2", "3", "4", "5"], "x")

content = service.client.sent[-1]["messages"][0]["content"]

check(
    "more blocks than the API's four breakpoints are folded, not dropped",
    [block["text"] for block in content if "cache_control" in block],
    ["1", "2", "3", "45"],
)

service.generate_text("one string")

check(
    "a plain call is unchanged",
    service.client.sent[-1]["messages"][0]["content"],
    "one string",
)

print()
print("=" * 80)
print("THE DEVELOPER'S BLOCKS ARE THE SAME BYTES ACROSS A TASK")
print("=" * 80)

llm = Caching()

factory.LLMFactory.create = classmethod(lambda cls, role="": llm)

Settings.GENERATE_FILE_BY_FILE = True

Settings.FILES_PER_CALL = 1

from agents.developer_agent import DeveloperAgent  # noqa: E402

root = tempfile.mkdtemp()

try:
    os.makedirs(os.path.join(root, "src"))

    with open(os.path.join(root, "src", "password-rule.ts"), "w", encoding="utf-8") as handle:
        handle.write("export interface PasswordRule { check(p: string): string | null; }\n")

    files = DeveloperAgent().execute("Add a BlocklistRule implementing PasswordRule.", root)

    plan_call, *file_calls = llm.calls

    check("a plan call, then one call per file", (len(file_calls), len(files)), (2, 2))

    check(
        "the plan call and every file call open with the same context block",
        {cached[0] for cached, _ in llm.calls} == {plan_call[0][0]},
        True,
    )

    check(
        "which holds the existing code the task names",
        "check(p: string): string | null" in plan_call[0][0],
        True,
    )

    check(
        "the file calls share the file list too",
        len({cached[1] for cached, _ in file_calls}),
        1,
    )

    check(
        "and differ only after the cached blocks",
        [prompt.splitlines()[1] for _, prompt in file_calls],
        [
            "Write exactly one of them: src/blocklist-rule.ts",
            "Write exactly one of them: src/common-passwords.ts",
        ],
    )

    print()
    print("=" * 80)
    print("THE ARCHITECT'S RULES ARE THE SAME IN EVERY REVIEW")
    print("=" * 80)

    from agents.architect_agent import RULES, ArchitectAgent  # noqa: E402

    llm.calls.clear()

    source = [GeneratedFile("src/blocklist-rule.ts", FileType.SOURCE, "export class BlocklistRule {}")]

    ArchitectAgent().execute("Task one.", source, [], root)

    ArchitectAgent().execute("A different task.", source, [], root)

    check(
        "both reviews send the rules as their cached block",
        [cached for cached, _ in llm.calls],
        [[RULES], [RULES]],
    )

    check(
        "and the rules hold nothing about the task",
        ("Task one" in RULES, "Task one." in llm.calls[0][1]),
        (False, True),
    )

finally:
    shutil.rmtree(root, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL PROMPT CACHE CHECKS PASSED")
print("=" * 80)
