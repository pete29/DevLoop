"""Offline checks: what the release smoke test writes.

The smoke test itself calls the real model; its one line and
where it lands in CHANGELOG.md are checked here, for free:

    python -m tests.smoke_record_test
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "evals"))

import smoke  # noqa: E402

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


print("=" * 80)
print("THE LINE")
print("=" * 80)

good = smoke.line({"planned": 2, "ran": 2, "good": 2, "run": "DONE", "scores": [92, 88], "cost": 0.0812})

check("every planned task good: passed, with scores and cost", ("passed" in good, "2/2" in good, "92, 88" in good, "$0.0812" in good), (True, True, True, True))

stopped = smoke.line({"planned": 2, "ran": 1, "good": 1, "run": "STOPPED: Task 1 breaks tests", "scores": [70], "cost": 0.05})

check("a run that stopped short failed, and says why", ("FAILED" in stopped, "breaks tests" in stopped), (True, True))

print()
print("=" * 80)
print("WHERE IT LANDS")
print("=" * 80)

path = os.path.join(tempfile.mkdtemp(), "CHANGELOG.md")

with open(path, "w", encoding="utf-8") as handle:
    handle.write("# Changelog\n\n## Unreleased\n\n### Fixed\n- a fix\n\n## 0.13.0 (alpha)\n\n- older\n")

smoke.record(good, path)

with open(path, encoding="utf-8") as handle:
    text = handle.read()

check("under Unreleased, in a Smoke test section of its own", text.index("### Smoke test") < text.index("### Fixed") < text.index("## 0.13.0"), True)

smoke.record(stopped, path)

with open(path, encoding="utf-8") as handle:
    text = handle.read()

check("a second run joins the same section", (text.count("### Smoke test"), text.count("- Smoke test")), (1, 2))

check("the released sections are left alone", text.endswith("## 0.13.0 (alpha)\n\n- older\n"), True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL SMOKE RECORD CHECKS PASSED")
print("=" * 80)
