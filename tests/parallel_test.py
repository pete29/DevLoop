"""Offline checks for a task's model calls running side by side.

    python -m tests.parallel_test
"""

import threading
import time

from config.settings import Settings
from services.parallel import run_all

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


class Recorder:
    """A slow call that notes when it ran and how many ran with it."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.running = 0
        self.most = 0
        self.started: dict[int, float] = {}
        self.finished: dict[int, float] = {}

    def __call__(self, item: int) -> int:
        with self.lock:
            self.running += 1
            self.most = max(self.most, self.running)
            self.started[item] = time.perf_counter()
        # Later items finish sooner, so the order of
        # finishing is not the order asked for.
        time.sleep(0.05 + 0.02 * (8 - item))
        with self.lock:
            self.running -= 1
            self.finished[item] = time.perf_counter()
        return item * 10


print("=" * 80)
print("SIDE BY SIDE, IN THE ORDER ASKED")
print("=" * 80)

Settings.PARALLEL_CALLS = 4

calls = Recorder()

results = run_all(list(range(8)), calls)

check("each answer is in its item's place", results, [item * 10 for item in range(8)])

check("the first ran alone, before any other started", all(calls.started[i] >= calls.finished[0] for i in range(1, 8)), True)

check("then several at once", calls.most > 1, True)

check("never more than the limit", calls.most <= 4, True)

print()
print("=" * 80)
print("ONE AT A TIME WHEN ASKED")
print("=" * 80)

Settings.PARALLEL_CALLS = 1

calls = Recorder()

check("the same answers", run_all(list(range(5)), calls), [item * 10 for item in range(5)])

check("one call at a time", calls.most, 1)

print()
print("=" * 80)
print("THE EDGES")
print("=" * 80)

Settings.PARALLEL_CALLS = 4

check("nothing to do, no calls", run_all([], lambda item: 1 / 0), [])

check("one item, one call", run_all([3], lambda item: item + 1), [4])


def failing(item: int) -> int:
    if item == 2:
        raise RuntimeError("the call failed")
    return item


try:
    run_all([0, 1, 2, 3], failing)
    failures.append("a failure is not swallowed")
    print("FAIL a failure is not swallowed")

except RuntimeError:
    print("OK   a failure is not swallowed")

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL PARALLEL CHECKS PASSED")
print("=" * 80)
