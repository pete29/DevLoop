"""Offline checks: the repository tools the developer and QA may call (#52).

A throwaway repository on disk, and a fake Anthropic client
that asks for files the way the model would; nothing is sent:

    python -m tests.repo_tools_test
"""

import os
import tempfile

from services import claude_service
from services.prompt_cache import ask
from services.repo_tools import RepoTools, for_repository

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


root = tempfile.mkdtemp()

for relative, content in {
    "src/parser.ts": "export const parse = 1;\n",
    "tests/parser.test.ts": "describe('parse', () => {});\n",
    ".env": "ANTHROPIC_API_KEY=sk-ant-secret\n",
    "node_modules/x/index.js": "module.exports = 1;\n",
    ".git/config": "[core]\n",
}.items():
    path = os.path.join(root, *relative.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)

print("=" * 80)
print("WHAT CAN BE READ")
print("=" * 80)

tools = RepoTools(root, budget=10)

check("a test beside the file under work", tools.run("read_file", {"path": "tests/parser.test.ts"}), ("describe('parse', () => {});\n", False))

check("backslashes work too", tools.run("read_file", {"path": "src\\parser.ts"})[1], False)

listing, failed = tools.run("list_files", {"folder": "."})

check("the listing has the code and the tests", (failed, "src/parser.ts" in listing, "tests/parser.test.ts" in listing), (False, True, True))

check("and never the keys, the dependencies or git's own files", any(name in listing for name in (".env", "node_modules", ".git/")), False)

print()
print("=" * 80)
print("WHAT IS REFUSED")
print("=" * 80)

for label, path in (
    ("the keys", ".env"),
    ("a dependency", "node_modules/x/index.js"),
    ("git's own files", ".git/config"),
    ("a file outside the repository", "../outside.txt"),
    ("an absolute path elsewhere", os.path.join(tempfile.gettempdir(), "x.txt")),
):
    text, failed = tools.run("read_file", {"path": path})
    check(f"{label}: refused", (failed, "secret" in text), (True, False))

check("a file that does not exist says so", tools.run("read_file", {"path": "src/none.ts"})[1], True)

check("an unknown tool is an error, not a crash", tools.run("delete_file", {"path": "src/parser.ts"})[1], True)

print()
print("=" * 80)
print("THE BUDGET")
print("=" * 80)

small = RepoTools(root, budget=2)

small.run("read_file", {"path": "src/parser.ts"})
small.run("read_file", {"path": "src/parser.ts"})

text, failed = small.run("read_file", {"path": "src/parser.ts"})

check("past the budget: no more reads, write now", (failed, "Write your answer now" in text), (True, True))

check("switched off, or without a folder, there are no tools", (for_repository(""), for_repository(os.path.join(root, "missing"))), (None, None))

print()
print("=" * 80)
print("THE CLAUDE CALL ANSWERS THE MODEL'S READS")
print("=" * 80)


class Usage:
    input_tokens = 10
    output_tokens = 5
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0


class ToolUse:
    type = "tool_use"

    def __init__(self, ident, name, arguments):
        self.id = ident
        self.name = name
        self.input = arguments


class Text:
    type = "text"

    def __init__(self, text):
        self.text = text


class Message:
    model = "claude-sonnet-5-5"
    usage = Usage()
    stop_details = None

    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason


class Stream:
    def __init__(self, message):
        self.message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self.message


class Client:
    """Answers with the scripted messages in turn, keeping what was sent."""

    def __init__(self, script):
        self.script = list(script)
        self.sent = []

        client = self

        class Messages:
            def stream(inner, **kwargs):
                client.sent.append(kwargs)
                return Stream(client.script.pop(0))

        class Beta:
            messages = Messages()

        self.beta = Beta()


def service(script):

    made = claude_service.ClaudeService.__new__(claude_service.ClaudeService)
    made.client = Client(script)
    made.model = "claude-sonnet-5-5"
    made.effort = "medium"
    made.role = "qa"
    return made


reader = service([
    Message([Text("Let me look."), ToolUse("t1", "read_file", {"path": "tests/parser.test.ts"})], "tool_use"),
    Message([Text("import { describe } from 'vitest';")], "end_turn"),
])

answer = ask(reader, ["context"], "Write the suite.", tools=RepoTools(root, budget=3))

check("the answer is the text after the reads", answer, "import { describe } from 'vitest';")

second = reader.client.sent[1]["messages"]

check(
    "the file went back as the tool's result, for the call it answers",
    (second[2]["content"][0]["tool_use_id"], "describe('parse'" in second[2]["content"][0]["content"]),
    ("t1", True),
)

check("the tools were offered, strict", [tool["name"] for tool in reader.client.sent[0]["tools"]] + [reader.client.sent[0]["tools"][0]["strict"]], ["read_file", "list_files", True])

check("and the prompt says how many reads it has", "at most 3 calls" in reader.client.sent[0]["messages"][0]["content"][-1]["text"], True)

stubborn = service([Message([ToolUse(f"t{n}", "read_file", {"path": "src/parser.ts"})], "tool_use") for n in range(5)])

try:
    ask(stubborn, [], "Write.", tools=RepoTools(root, budget=1))
    stopped = False
except RuntimeError as error:
    stopped = "kept asking" in str(error)

check("a model that keeps asking past the budget is stopped, not paid for forever", (stopped, len(stubborn.client.sent)), (True, 3))

plain = service([Message([Text("done")], "end_turn")])

ask(plain, ["context"], "Write.")

check("without tools, nothing about them is sent", "tools" in plain.client.sent[0], False)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL REPO TOOLS CHECKS PASSED")
print("=" * 80)
