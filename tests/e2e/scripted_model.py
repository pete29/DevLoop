"""The model, scripted: what each agent is told to say.

A small two-task requirement -- day arithmetic, then the
weekday built on it -- answered the way the agents expect:
the planner in its JSON, the developer a file plan then
plain TypeScript, the architect in its text format, QA a
suite. The code is real and correct, so the real compiler
and test runner pass it.
"""

import json
import re

PLAN = {
    "files": [
        {
            "path": "1",
            "content": "Add day arithmetic",
            "description": "Add addDays(iso, n) in src/days.ts, returning the ISO date n days later.",
            "priority": "HIGH",
            "dependencies": [],
            "creates": ["src/days.ts"],
            "modifies": [],
        },
        {
            "path": "2",
            "content": "Add the weekday",
            "description": "Add weekdayOf(iso) in src/weekday.ts, Monday = 1 to Sunday = 7, using addDays.",
            "priority": "MEDIUM",
            "dependencies": [1],
            "creates": ["src/weekday.ts"],
            "modifies": [],
        },
    ]
}

SOURCES = {
    "src/days.ts": (
        "export function addDays(iso: string, n: number): string {\n"
        "  const date = new Date(`${iso}T00:00:00Z`);\n"
        "  date.setUTCDate(date.getUTCDate() + n);\n"
        "  return date.toISOString().slice(0, 10);\n"
        "}\n"
    ),
    # Imports by the compiled name, as the day the factory
    # first failed: it must be read as src/days.ts.
    "src/weekday.ts": (
        'import { addDays } from "./days.js";\n'
        "\n"
        "export function weekdayOf(iso: string): number {\n"
        "  const day = new Date(`${addDays(iso, 0)}T00:00:00Z`).getUTCDay();\n"
        "  return day === 0 ? 7 : day;\n"
        "}\n"
    ),
}

SUITES = {
    "src/days.ts": (
        "addDays",
        "describe('addDays', () => {\n"
        "  it('crosses a month', () => {\n"
        "    expect(addDays('2024-01-31', 1)).toBe('2024-02-01');\n"
        "  });\n"
        "});\n",
    ),
    "src/weekday.ts": (
        "weekdayOf",
        "describe('weekdayOf', () => {\n"
        "  it('knows a Monday', () => {\n"
        "    expect(weekdayOf('2024-01-01')).toBe(1);\n"
        "  });\n"
        "});\n",
    ),
}

REVIEW = """SCORE: 92

RECOMMENDATION:
APPROVE

RESOLVED FINDINGS:
- None

BLOCKERS:
- None

WARNINGS:
- None

SUGGESTIONS:
- None
"""


class ScriptedModel:
    """One agent's model. Every prompt it is sent is kept."""

    def __init__(self, role: str, log: list[tuple[str, str]]) -> None:

        self.role = role

        self.log = log

    def generate_text(self, prompt: str) -> str:

        self.log.append((self.role, prompt))

        if self.role == "planner":
            return json.dumps(PLAN)

        if self.role == "architect":
            return REVIEW

        if self.role == "qa":
            return self.suite(prompt)

        return self.developer(prompt)

    def generate_code(self, prompt: str) -> str:

        return ""

    @staticmethod
    def task_file(prompt: str) -> str:
        """The file the task in the prompt is about."""

        return "src/weekday.ts" if "weekdayOf" in prompt else "src/days.ts"

    def developer(self, prompt: str) -> str:

        if "no code at this stage" in prompt:

            path = self.task_file(prompt)

            return json.dumps({"files": [{"path": path, "content": f"Implements {path}."}]})

        asked = re.search(r"Write exactly one of them: (\S+)", prompt)

        return SOURCES[asked.group(1) if asked else self.task_file(prompt)]

    @staticmethod
    def suite(prompt: str) -> str:

        lines = prompt.splitlines()

        source = next(
            lines[index + 1].strip()
            for index, line in enumerate(lines)
            if line.startswith("Write a Vitest suite for exactly one")
        )

        specifier = re.search(r"import \{\{? ?\.\.\. ?\}?\} from '([^']+)'", prompt).group(1)

        name, body = SUITES[source]

        return (
            "import { describe, it, expect } from 'vitest';\n"
            f"import {{ {name} }} from '{specifier}';\n"
            "\n" + body
        )
