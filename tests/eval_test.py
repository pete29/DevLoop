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

print("=" * 80)
print("A CASE'S OWN FILES, AND THE DATEPICKER CASES")
print("=" * 80)

import json as _json  # noqa: E402
import os as _os  # noqa: E402
import shutil as _shutil  # noqa: E402
import tempfile as _tempfile  # noqa: E402

from evals.run_eval import apply_setup  # noqa: E402

work = _tempfile.mkdtemp()

try:
    written = apply_setup({"setup": {"src/index.ts": "export type { A } from './a.js';"}}, work)

    with open(_os.path.join(work, "src", "index.ts"), encoding="utf-8") as handle:
        check("a setup file is written into the copy", (written, handle.read()), (["src/index.ts"], "export type { A } from './a.js';"))

    refused = False
    try:
        apply_setup({"setup": {"../outside.ts": "x"}}, work)
    except ValueError:
        refused = True
    check("and never outside it", refused, True)

finally:
    _shutil.rmtree(work, ignore_errors=True)

ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))

with open(_os.path.join(ROOT, "evals", "cases.json"), encoding="utf-8") as handle:
    ids = [case["id"] for case in _json.load(handle)]

check(
    "what broke on datepicker is in the eval",
    all(case in ids for case in ("js-extension-import", "barrel-types", "dom-render", "html-page")),
    True,
)

print()
print("=" * 80)
from evals.run_eval import parse_arguments  # noqa: E402

check("a label, cases to run and a budget", parse_arguments(["v2", "--only=a,b", "--budget=0.4"]), {"label": "v2", "only": {"a", "b"}, "budget": 0.4})

check("by default every case, no budget", parse_arguments([]), {"label": "run", "only": set(), "budget": 0.0})

print("ALL EVAL CHECKS PASSED")
print("=" * 80)
