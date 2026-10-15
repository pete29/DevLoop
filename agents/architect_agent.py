import json

from models.architecture_review import (
    ArchitectureReview,
)
from models.generated_file import GeneratedFile
from models.review_history import (
    ReviewHistory,
)
from services.file_bundle import FileBundle
from services.finding_filter import cap, drop_structural
from services.llm_factory import (
    LLMFactory,
)
from services.prompt_cache import ask, ask_json
from services.repository_survey import survey
from services.review_history_formatter import (
    ReviewHistoryFormatter,
)
from services.review_parser import (
    ReviewParser,
    drop_contradictions,
)
from services.structure_validator import (
    StructureValidator,
)
from workflows.recommendation_policy import (
    RecommendationPolicy,
)
from workflows.review_decision import (
    ReviewDecision,
)


# Everything about how to review, and nothing about what:
# identical bytes in every call.
#
# Three findings of two sentences, suggestions only when
# worth a revision: output tokens are the bill, and on
# four real reviews this cut them from 3752 to 2291 (-32%
# in dollars) with the same main findings. Lowering the
# effort instead saved 5% and missed more, so it stays.
RULES_BODY = """
You are a Senior Software Architect.

Review the project structure as well as the
code. A file set should separate interfaces,
services and providers, and each file should
hold one logical component.

Review only what cannot be checked
mechanically:

- dependency inversion and dependency
  boundaries
- the Open/Closed and Single Responsibility
  principles
- separation of concerns
- abstraction quality and pattern choice
- naming
- extensibility and maintainability

DO NOT report:

- missing files
- missing imports
- missing symbols
- requirement coverage
- compilation problems

A structural validator already owns those,
and repeating them makes the review wrong as
often as it makes it right.

Report at most 3 findings in total: the
ones that matter most. Write each finding in
at most two sentences - what is wrong, and
what to change. Leave SUGGESTIONS as "None"
unless one is worth a revision.

Classify every finding by severity.

BLOCKER
Prevents the solution from meeting
architectural, functional, security,
reliability or maintainability
requirements.

Always a BLOCKER:

- a dependency inversion violation
- a broken abstraction boundary
- a hard-coded infrastructure dependency
- invalid business logic
- a security vulnerability
- unbounded resource consumption

WARNING
Should be fixed, but does not make the
implementation unacceptable. For example:
missing logging, weak naming, missing
documentation, limited extensibility,
non-optimal design choices, a file holding
several unrelated components.

SUGGESTION
Optional improvement. For example: pattern
recommendations, performance ideas, code
style, future-proofing.

Rules:

- A BLOCKER is an architectural decision that
  must change before this ships, not a
  missing file.
- When in doubt choose WARNING over BLOCKER.
- Missing logging, error handling, retries,
  metrics and tests are WARNINGS or
  SUGGESTIONS, never BLOCKERS, unless the
  task explicitly asked for them.
- "Could be more extensible" and "could be
  more generic" are SUGGESTIONS.
- If there are no previous reviews, review
  the code from scratch and leave RESOLVED
  FINDINGS as "None".
- Otherwise take every finding from the
  most recent previous review one by one.
  If the current code addresses it, list it
  under RESOLVED FINDINGS and do not repeat
  it. If it is not addressed, list it again
  under its severity. Never silently drop a
  previous finding.
- A finding counts as resolved as soon as
  the current code addresses it, even if
  the solution is not perfect.
- RESOLVED FINDINGS is only for findings
  that are genuinely fixed. Never list the
  same finding under RESOLVED FINDINGS and
  under a severity heading. Never write
  "(not resolved)" or a similar note there.
  Each finding appears under exactly one
  heading.
- Do not re-raise a finding you already
  listed as resolved in an earlier review.
- Raise the score when findings are
  resolved.
- Write "None" under a heading that has no
  entries.
- Write every finding in English, even when
  the task or the code is in another
  language. Your answer is parsed by English
  rules.
- One finding is one bullet holding one
  paragraph. Never put a list inside a
  finding: write examples and cases as
  sentences, separated by semicolons.

"""

# How to answer in text, for a provider without structured
# outputs. Claude answers in the schema below instead.
TEXT_FORMAT = """Return exactly in this format, with no
extra commentary:

SCORE: <0-100>

RECOMMENDATION: <APPROVE|REQUEST_CHANGES|REJECT>

RESOLVED FINDINGS:
- previously raised finding that is now fixed

BLOCKERS:
- finding

WARNINGS:
- finding

SUGGESTIONS:
- finding
"""

RULES = RULES_BODY + TEXT_FORMAT

JSON_FORMAT = """Answer with the JSON the schema describes:
the score from 0 to 100; the recommendation;
under resolved, the findings of the most recent
previous review that the current code fixes;
under findings, every open finding, each with
its severity (BLOCKER, WARNING or SUGGESTION),
the file it is about ("" when it is about no
one file), and the finding itself. Empty lists
where there is nothing.
"""

# The review's shape, enforced by the API: nothing to parse
# out of prose, no list inside a finding to split, no
# heading to miss.
REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "score": {"type": "integer"},
        "recommendation": {
            "type": "string",
            "enum": ["APPROVE", "REQUEST_CHANGES", "REJECT"],
        },
        "resolved": {"type": "array", "items": {"type": "string"}},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["BLOCKER", "WARNING", "SUGGESTION"],
                    },
                    "file": {"type": "string"},
                    "finding": {"type": "string"},
                },
                "required": ["severity", "file", "finding"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["score", "recommendation", "resolved", "findings"],
    "additionalProperties": False,
}


def from_json(answer: dict) -> tuple[int, str, list[str], list[str], list[str], list[str]]:
    """Score, recommendation and the four lists from a JSON review.

    A finding about a file says which, so the developer's
    next round rewrites that file.
    """

    def text(item: dict) -> str:

        finding = " ".join(str(item.get("finding") or "").split())

        path = str(item.get("file") or "").strip()

        return f"{path}: {finding}" if path and finding else finding

    def of(severity: str) -> list[str]:

        return [
            text(item)
            for item in answer.get("findings") or []
            if item.get("severity") == severity and text(item)
        ]

    score = max(0, min(100, int(answer.get("score") or 0)))

    resolved = [
        " ".join(str(item).split())
        for item in answer.get("resolved") or []
        if str(item).strip()
    ]

    return (
        score,
        str(answer.get("recommendation") or ""),
        resolved,
        of("BLOCKER"),
        of("WARNING"),
        of("SUGGESTION"),
    )


def _as_lines(findings: list[str]) -> str:

    if not findings:
        return "- None"

    return "\n".join(f"- {finding}" for finding in findings)


class ArchitectAgent:
    def __init__(
        self,
    ) -> None:

        self.llm = (
            LLMFactory.create("architect")
        )

    def execute(
        self,
        task_description: str,
        source_files: list[GeneratedFile],
        review_history: list[
            ReviewHistory
        ] | None = None,
        repository_path: str = "",
    ) -> ArchitectureReview:

        history = review_history or []

        history_text = (
            ReviewHistoryFormatter.format(
                history
            )
        )

        # Imports, missing files and requirement coverage
        # are facts about the file set, so they are decided
        # here rather than left to the model.
        # What is already in the repository counts as
        # known. Without it, importing a file an earlier
        # task wrote reads as importing a file that does
        # not exist, and the loop spends a round chasing a
        # problem nobody has.
        found = survey(repository_path)

        report = StructureValidator.validate(
            source_files,
            task_description,
            found,
        )

        # The code this task builds on, so a review of a
        # class that implements PasswordRule can see what
        # PasswordRule is. Context, not under review.
        builds_on = found.render_referenced(
            task_description,
            {item.path for item in source_files},
        )

        structural_findings = report.blockers

        # The rules first, word for word the same in every
        # review, so every task of a plan reads them from the
        # cache; what is under review comes after.
        prompt = f"""

Task:
{task_description}

Previous Reviews:

{history_text}

Project Structure:

{FileBundle.structure(source_files)}

Repository Validation Report:

{report.summary()}

A compiler-style pass has already checked
this file set and recorded the problems
below. They are handled. Do not repeat them,
and do not look for more of their kind:

{_as_lines(structural_findings)}

Current Code:

{FileBundle.render(source_files)}
{builds_on}
Review it by the rules above, and answer in
exactly the format they give.
"""

        answer = ask_json(
            self.llm,
            [RULES_BODY + JSON_FORMAT],
            prompt,
            REVIEW_SCHEMA,
        )

        if answer is not None:

            (
                score,
                stated,
                resolved,
                blockers,
                warnings,
                suggestions,
            ) = from_json(answer)

            raw_review = json.dumps(answer, ensure_ascii=False, indent=2)

        else:

            raw_review = ask(self.llm, [RULES], prompt)

            score = ReviewParser.score(raw_review)

            resolved = ReviewParser.section(
                raw_review, "resolved"
            )

            blockers = ReviewParser.section(
                raw_review, "blockers"
            )

            warnings = ReviewParser.section(
                raw_review, "warnings"
            )

            suggestions = ReviewParser.section(
                raw_review, "suggestions"
            )

            stated = ReviewParser.stated_recommendation(
                raw_review
            )

        # Structural findings come from the validator
        # alone. Anything the model says about missing
        # files, imports or symbols is dropped, because it
        # read the code while the validator checked it.
        structural = structural_findings

        blockers = cap(
            drop_structural(blockers, "blockers"),
            "blockers",
        )

        warnings = cap(
            drop_structural(warnings, "warnings"),
            "warnings",
        )

        suggestions = cap(
            drop_structural(suggestions, "suggestions"),
            "suggestions",
        )

        # A finding cannot be resolved and open at
        # the same time; still being open wins.
        resolved = drop_structural(
            drop_contradictions(
                resolved,
                blockers
                + warnings
                + suggestions
                + structural,
            ),
            "resolved findings",
        )

        recommendation = RecommendationPolicy.decide(
            blockers,
            structural,
            ReviewDecision(stated) if stated else None,
        )

        review_text = self._render(
            resolved,
            blockers,
            warnings,
            suggestions,
        )

        print("=" * 80)
        print(
            "ARCHITECT RESULT "
            f"(iteration {len(history) + 1}, "
            f"{len(history)} previous reviews)"
        )
        print("=" * 80)
        print(
            f"score={score} "
            f"blockers={len(blockers)} "
            f"warnings={len(warnings)} "
            f"suggestions={len(suggestions)} "
            f"structural={len(structural)} "
            f"resolved={len(resolved)} "
            f"stated={stated} "
            f"-> {recommendation.value}"
        )
        print("=" * 80)
        print(raw_review)
        print("=" * 80)

        return ArchitectureReview(
            score=score,
            recommendation=recommendation,
            review=review_text,
            resolved=resolved,
            blockers=blockers,
            warnings=warnings,
            suggestions=suggestions,
            structural=structural,
            structure_report=report,
        )

    @staticmethod
    def _render(
        resolved: list[str],
        blockers: list[str],
        warnings: list[str],
        suggestions: list[str],
    ) -> str:

        sections = (
            ("Resolved Findings", resolved),
            ("Blockers", blockers),
            ("Warnings", warnings),
            ("Suggestions", suggestions),
        )

        parts: list[str] = []

        for title, findings in sections:

            if findings:
                body = "\n".join(
                    f"- {finding}"
                    for finding in findings
                )
            else:
                body = "- None"

            parts.append(f"**{title}:**\n{body}")

        return "\n\n".join(parts)
