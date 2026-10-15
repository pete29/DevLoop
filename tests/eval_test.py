"""Offline checks for the eval's verdict and its reports.

No model is called; the eval itself (evals/run_eval.py) is
never run here.

    python -m tests.eval_test
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evals"))

from compare import compare  # noqa: E402
from run_eval import passed, table  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


GOOD = {
    "id": "lowercase-rule",
    "compile": "PASSED",
    "tests": "PASSED",
    "tests_passed": 21,
    "tests_total": 21,
    "score": 95,
    "recommendation": "APPROVE",
    "review_rounds": 1,
    "cost": 0.0279,
    "output_tokens": 938,
    "seconds": 18.7,
}

check("built, tested and approved is a pass", passed(GOOD), True)

check("failing tests are not", passed({**GOOD, "tests": "FAILED"}), False)

check("nor is a request for changes", passed({**GOOD, "recommendation": "REQUEST_CHANGES"}), False)

check("nor is an error", passed({"id": "x", "error": "boom"}), False)

before = {
    "results": [{**GOOD, "passed": True}],
    "passed": 1,
    "total_cost": 0.0279,
}

after = {
    "results": [{**GOOD, "passed": False, "score": 70, "review_rounds": 3, "cost": 0.09}],
    "passed": 0,
    "total_cost": 0.09,
}

report = table({**after, "results": after["results"] + [{"id": "broken", "error": "the model refused", "passed": False}]})

check("the table has a row per case, an error included", ("lowercase-rule" in report, "ERROR: the model refused" in report), (True, True))

check("and the total", "0/2 passed, $0.0900 in all" in report, True)

noted = table(
    {
        "results": [
            {**GOOD, "id": "hash-password", "passed": True, "packages_asked": ["@types/node"]},
            {**GOOD, "id": "policy-plan", "passed": True, "tasks": 3, "plan_problems": ["x"]},
        ],
        "passed": 2,
        "total_cost": 0.1,
    }
)

check(
    "a case notes the packages it asked for, a plan its tasks and problems",
    ("asked for @types/node" in noted, "3 tasks, 1 plan problems" in noted),
    (True, True),
)

diff = compare(before, after)

check(
    "a comparison shows what changed, per case and in total",
    ("True -> False" in diff, "95 -> 70" in diff, "1 -> 3" in diff, "cost $0.0279 -> $0.0900" in diff),
    (True, True, True, True),
)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL EVAL CHECKS PASSED")
print("=" * 80)
