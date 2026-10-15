from dataclasses import dataclass

from services.file_parser import FileParseError, FileParser
from services.llm_factory import LLMFactory

MIN_STORIES = 2

MAX_STORIES = 6

MAX_TITLE = 80

PROMPT = """
You are a Product Owner.

This requirement is too large for one pull request.
Split it into user stories, each of which a developer
can deliver, review and merge on its own.

Requirement:
{requirement}

Rules:

- between {minimum} and {maximum} stories
- each story is a vertical slice that is useful and
  testable by itself, not a technical layer such as
  "write the interfaces"
- order them so a story only builds on stories before
  it; say so in its body when it does
- every story has a short title and a body with a
  description and a list of acceptance criteria
- cover the whole requirement, and nothing it does
  not ask for
- write in the language of the requirement
- do not plan project setup, deployment or
  documentation unless the requirement asks for it

Return only JSON in exactly this shape:

{{
  "stories": [
    {{
      "title": "Short title",
      "body": "What and why.\\n\\nAcceptance criteria:\\n- first\\n- second"
    }}
  ]
}}
"""


@dataclass
class Story:
    """One slice of a large requirement, to become an issue."""

    title: str

    body: str


class StorySplitter:
    """Proposes how to split a requirement into issues.

    Only proposes: a human reads, edits and picks the
    stories before any issue is created. What is checked
    here are the facts -- how many, whether each has a
    title, whether two are the same.
    """

    def __init__(self) -> None:

        self.llm = LLMFactory.create("planner")

    def execute(self, requirement: str) -> list[Story]:

        raw = self.llm.generate_text(
            PROMPT.format(
                requirement=requirement,
                minimum=MIN_STORIES,
                maximum=MAX_STORIES,
            )
        )

        return self.parse(raw)

    @staticmethod
    def parse(raw: str) -> list[Story]:

        try:
            payload = FileParser.load(
                FileParser.extract_json(raw)
            )

        except (FileParseError, ValueError) as error:
            raise RuntimeError(
                f"No usable split in the answer: {error}"
            ) from error

        entries = payload.get("stories")

        if not isinstance(entries, list):
            raise RuntimeError("No stories in the answer.")

        stories: list[Story] = []

        seen: set[str] = set()

        for entry in entries:

            if not isinstance(entry, dict):
                continue

            title = " ".join(str(entry.get("title") or "").split())

            body = str(entry.get("body") or "").strip()

            if not title or title.lower() in seen:
                continue

            seen.add(title.lower())

            stories.append(
                Story(title=title[:MAX_TITLE], body=body)
            )

        if len(stories) < MIN_STORIES:
            raise RuntimeError(
                "The answer did not split the requirement: "
                f"{len(stories)} usable story(ies)."
            )

        return stories[:MAX_STORIES]


def children_comment(created: list[tuple[int, str]]) -> str:
    """The parent issue's view of its split, as a task list.

    GitHub renders "- [ ] #12" as a tracked item that ticks
    itself when #12 is closed.
    """

    return "\n".join(
        [
            "Split by DevLoop into:",
            "",
            *[f"- [ ] #{number} {title}" for number, title in created],
        ]
    )


def child_body(story: Story, parent: int) -> str:
    """A story's issue body, pointing back at its parent."""

    if parent <= 0:
        return story.body

    return f"{story.body}\n\nPart of #{parent}."
