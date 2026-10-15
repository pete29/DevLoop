"""Offline checks for the Architect's structured (JSON) review.

    python -m tests.structured_review_test
"""

import os
import shutil
import tempfile

import services.llm_factory as factory
from models.file_type import FileType
from models.generated_file import GeneratedFile
from workflows.review_decision import ReviewDecision

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


ANSWER = {
    "score": 140,
    "recommendation": "REQUEST_CHANGES",
    "resolved": ["  The validator   now takes its rules.  "],
    "findings": [
        {"severity": "BLOCKER", "file": "src/rule.ts", "finding": "It imports the concrete store."},
        {"severity": "WARNING", "file": "", "finding": "Naming is inconsistent across rules."},
        {"severity": "SUGGESTION", "file": "src/rule.ts", "finding": "Inject the message."},
        {"severity": "WARNING", "file": "src/rule.ts", "finding": "  "},
    ],
}


class Structured:
    def __init__(self):
        self.calls = []

    def generate_text(self, prompt):
        raise AssertionError("a provider with structured outputs is asked for JSON")

    def generate_json(self, cached, prompt, schema):
        self.calls.append((cached, prompt, schema))
        return ANSWER


llm = Structured()

factory.LLMFactory.create = classmethod(lambda cls, role="": llm)

from agents.architect_agent import (  # noqa: E402
    JSON_FORMAT,
    REVIEW_SCHEMA,
    RULES,
    RULES_BODY,
    ArchitectAgent,
)

root = tempfile.mkdtemp()

try:

    print("=" * 80)
    print("THE ARCHITECT ANSWERS IN A SCHEMA")
    print("=" * 80)

    review = ArchitectAgent().execute(
        "Create the rule.",
        [GeneratedFile("src/rule.ts", FileType.SOURCE, "export class Rule {}")],
        [],
        root,
    )

    cached, prompt, schema = llm.calls[0]

    check("the schema goes with the call", schema, REVIEW_SCHEMA)

    check(
        "with the rules and the JSON instructions as the cached block, not the text format",
        (cached, "Return exactly in this format" in cached[0]),
        ([RULES_BODY + JSON_FORMAT], False),
    )

    check("the text path keeps the text format", "Return exactly in this format" in RULES, True)

    check("the score is clamped", review.score, 100)

    check(
        "findings land by severity, with their file, empty ones dropped",
        (review.blockers, review.warnings, review.suggestions),
        (
            ["src/rule.ts: It imports the concrete store."],
            ["Naming is inconsistent across rules."],
            ["src/rule.ts: Inject the message."],
        ),
    )

    check("resolved findings are tidied", review.resolved, ["The validator now takes its rules."])

    check("a blocker still decides the recommendation", review.recommendation, ReviewDecision.REQUEST_CHANGES)

    check(
        "the review text reads as before",
        review.review.splitlines()[3:5],
        ["**Blockers:**", "- src/rule.ts: It imports the concrete store."],
    )

    print()
    print("=" * 80)
    print("THE SCHEMA IS ONE THE API ACCEPTS")
    print("=" * 80)

    def objects(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                yield node
            for value in node.values():
                yield from objects(value)
        elif isinstance(node, list):
            for value in node:
                yield from objects(value)

    check(
        "every object forbids additional properties and requires all its fields",
        all(
            node.get("additionalProperties") is False
            and set(node.get("required", [])) == set(node.get("properties", {}))
            for node in objects(REVIEW_SCHEMA)
        ),
        True,
    )

    print()
    print("=" * 80)
    print("CLAUDE SENDS THE FORMAT")
    print("=" * 80)

    from services import claude_service  # noqa: E402

    sent = []

    class Stream:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get_final_message(self):
            class Usage:
                input_tokens = output_tokens = cache_read_input_tokens = cache_creation_input_tokens = 0

            class Block:
                type = "text"
                text = '{"score": 90, "recommendation": "APPROVE", "resolved": [], "findings": []}'

            class Message:
                model = "claude-opus-5-5"
                usage = Usage()
                content = [Block()]
                stop_reason = "end_turn"
                stop_details = None

            return Message()

    class Client:
        class beta:
            class messages:
                @staticmethod
                def stream(**kwargs):
                    sent.append(kwargs)
                    return Stream()

    service = claude_service.ClaudeService.__new__(claude_service.ClaudeService)
    service.client = Client()
    service.model = "claude-opus-5-5"
    service.effort = "high"
    service.role = "architect"

    parsed = service.generate_json(["rules"], "review this", REVIEW_SCHEMA)

    check("the answer comes back as a dict", parsed["score"], 90)

    check(
        "and the request carried the schema next to the effort",
        sent[-1]["output_config"],
        {"effort": "high", "format": {"type": "json_schema", "schema": REVIEW_SCHEMA}},
    )

    check(
        "with the cached block marked",
        [("cache_control" in block) for block in sent[-1]["messages"][0]["content"]],
        [True, False],
    )

finally:
    shutil.rmtree(root, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL STRUCTURED REVIEW CHECKS PASSED")
print("=" * 80)
