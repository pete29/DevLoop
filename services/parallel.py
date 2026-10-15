"""Model calls of one task, side by side.

The developer wrote a task's files one call after another,
and QA its suites the same way, though no call needs
another's answer. Here they overlap: the folder is still
worked on by one task at a time, only the waiting for the
model is shared.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

from config.settings import Settings

Item = TypeVar("Item")

Result = TypeVar("Result")


def run_all(items: list[Item], call: Callable[[Item], Result]) -> list[Result]:
    """call(item) for each item; the results in the items' order.

    The first runs alone. Its prompt shares a cached prefix
    with all the others, and calls sent together would each
    miss the cache and pay to write it; after the first, the
    rest read it. Then at most PARALLEL_CALLS at once, which
    keeps a burst inside the API's rate limits. 1 runs them
    in turn, as before.
    """

    if not items:
        return []

    limit = max(1, int(Settings.PARALLEL_CALLS or 1))

    if limit == 1 or len(items) == 1:
        return [call(item) for item in items]

    first = call(items[0])

    with ThreadPoolExecutor(max_workers=min(limit, len(items) - 1)) as pool:
        rest = list(pool.map(call, items[1:]))

    return [first, *rest]
