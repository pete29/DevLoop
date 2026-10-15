"""Two eval reports side by side, per case and in total.

    python evals/compare.py evals/reports/before.json evals/reports/after.json
"""

import json
import sys


def load(path: str) -> dict:

    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def compare(before: dict, after: dict) -> str:

    rows = [
        f"{'case':22} {'passed':>13} {'score':>11} {'rounds':>9} {'cost':>21}",
    ]

    old = {r["id"]: r for r in before["results"]}

    for new in after["results"]:

        was = old.get(new["id"], {})

        def pair(key, fmt="{}"):
            a = was.get(key, "-")
            b = new.get(key, "-")
            a = fmt.format(a) if a != "-" else a
            b = fmt.format(b) if b != "-" else b
            return f"{a} -> {b}"

        rows.append(
            f"{new['id']:22} {pair('passed'):>13} {pair('score'):>11} "
            f"{pair('review_rounds'):>9} {pair('cost', '${:.4f}'):>21}"
        )

    rows.append("")

    rows.append(
        f"passed {before['passed']}/{len(before['results'])} -> "
        f"{after['passed']}/{len(after['results'])}; "
        f"cost ${before['total_cost']:.4f} -> ${after['total_cost']:.4f}"
    )

    return "\n".join(rows)


if __name__ == "__main__":

    if len(sys.argv) != 3:
        sys.exit(__doc__)

    print(compare(load(sys.argv[1]), load(sys.argv[2])))
