"""Offline checks for the severity model.

Runs without an LLM:

    python -m tests.severity_test
"""

from services.review_parser import (
    ReviewParser,
    drop_contradictions,
)
from workflows.recommendation_policy import (
    RecommendationPolicy,
)
from workflows.review_decision import (
    ReviewDecision,
)

RAW = """SCORE: 90

RECOMMENDATION:
REQUEST_CHANGES

RESOLVED FINDINGS:
- Tight coupling

BLOCKERS:
- None

WARNINGS:
- Missing logging

SUGGESTIONS:
- Consider strategy pattern
"""

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


print("=" * 80)
print("PARSER")
print("=" * 80)

check("score", ReviewParser.score(RAW), 90)

check(
    "stated recommendation",
    ReviewParser.stated_recommendation(RAW),
    "REQUEST_CHANGES",
)

check(
    "resolved",
    ReviewParser.section(RAW, "resolved"),
    ["Tight coupling"],
)

check(
    "blockers (None becomes empty)",
    ReviewParser.section(RAW, "blockers"),
    [],
)

check(
    "warnings",
    ReviewParser.section(RAW, "warnings"),
    ["Missing logging"],
)

check(
    "suggestions",
    ReviewParser.section(RAW, "suggestions"),
    ["Consider strategy pattern"],
)

# From the first live run: a finding that introduces a
# list, written at the same indent as the findings.
LISTED = """WARNINGS:
- Matches invisible characters. In practice it gives false positives:
- An NFD password passes.
- A trailing newline passes.

SUGGESTIONS:
- Accept the message in the constructor.
- Share a PatternRule.
"""

check(
    "a list inside a finding stays in that finding",
    ReviewParser.section(LISTED, "warnings"),
    [
        "Matches invisible characters. In practice it gives "
        "false positives: An NFD password passes. A trailing "
        "newline passes."
    ],
)

check(
    "findings without a colon are still separate",
    ReviewParser.section(LISTED, "suggestions"),
    [
        "Accept the message in the constructor.",
        "Share a PatternRule.",
    ],
)

print()
print("=" * 80)
print("RECOMMENDATION RULES")
print("=" * 80)

check(
    "rule 1: a blocker requests changes",
    RecommendationPolicy.decide(["tight coupling"]),
    ReviewDecision.REQUEST_CHANGES,
)

check(
    "rule 2 and 3: no blocker approves",
    RecommendationPolicy.decide([]),
    ReviewDecision.APPROVE,
)

check(
    "a blocker overrides a stated APPROVE",
    RecommendationPolicy.decide(
        ["security hole"],
        [],
        ReviewDecision.APPROVE,
    ),
    ReviewDecision.REQUEST_CHANGES,
)

check(
    "no blocker overrides stated REQUEST_CHANGES",
    RecommendationPolicy.decide(
        [],
        [],
        ReviewDecision.REQUEST_CHANGES,
    ),
    ReviewDecision.APPROVE,
)

check(
    "an explicit REJECT is kept",
    RecommendationPolicy.decide(
        [],
        [],
        ReviewDecision.REJECT,
    ),
    ReviewDecision.REJECT,
)

print()
print("=" * 80)
print("CONTRADICTION GUARD")
print("=" * 80)

check(
    "a hedged resolved finding is dropped",
    drop_contradictions(
        ["Tight coupling (not resolved)"],
        ["Tight coupling"],
    ),
    [],
)

check(
    "a genuinely resolved finding is kept",
    drop_contradictions(
        ["Tight coupling"],
        ["Missing logging"],
    ),
    ["Tight coupling"],
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL SEVERITY CHECKS PASSED")
print("=" * 80)
