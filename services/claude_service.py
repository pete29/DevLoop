import json

import anthropic

from config.settings import Settings
from services import usage_ledger
from services.code_cleaner import strip_code_fences

# On a policy decline the API re-runs the same request on
# a model chosen by the decline's category, inside the same
# call. Without it a refused request simply stops, and a
# twelve-file task loses whichever file it was on.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# The API allows four cache breakpoints per request.
MAX_CACHED_BLOCKS = 4


class ClaudeService:
    def __init__(
        self,
        model: str = "",
        effort: str = "",
        role: str = "",
    ) -> None:

        # The key is read from ANTHROPIC_API_KEY, which
        # app.py loads from .env. Never from settings: that
        # file is committed.
        self.client = anthropic.Anthropic()

        self.model = model or Settings.CLAUDE_MODEL

        self.effort = effort or Settings.CLAUDE_EFFORT

        self.role = role

    def generate_text(
        self,
        prompt: str,
    ) -> str:

        return self._call(prompt)

    def generate_cached(
        self,
        cached: list[str],
        prompt: str,
    ) -> str:
        """The same call, with `cached` as reusable blocks.

        Each block ends in a cache breakpoint, so a later
        call that starts with the same blocks reads them
        from the cache. Blocks beyond the API's limit are
        folded into the last one rather than dropped.
        """

        return self._call(self._blocks(cached, prompt))

    def generate_json(
        self,
        cached: list[str],
        prompt: str,
        schema: dict,
    ) -> dict:
        """An answer constrained to `schema`, as a dict.

        Structured outputs: the API guarantees valid JSON in
        that shape, so nothing has to be parsed out of prose.
        """

        return json.loads(
            self._call(
                self._blocks(cached, prompt),
                {"type": "json_schema", "schema": schema},
            )
        )

    def _blocks(self, cached: list[str], prompt: str) -> list[dict]:

        blocks = [block for block in cached if block.strip()]

        if len(blocks) > MAX_CACHED_BLOCKS:
            blocks = blocks[: MAX_CACHED_BLOCKS - 1] + [
                "".join(blocks[MAX_CACHED_BLOCKS - 1 :])
            ]

        return [
            {
                "type": "text",
                "text": block,
                "cache_control": {"type": "ephemeral"},
            }
            for block in blocks
        ] + [{"type": "text", "text": prompt}]

    def _call(self, content, output_format: dict | None = None) -> str:

        output_config = {"effort": self.effort}

        if output_format is not None:
            output_config["format"] = output_format

        # Streamed, because one file of real code can run
        # long enough to hit the HTTP timeout of a single
        # non-streaming request.
        with self.client.beta.messages.stream(
            model=self.model,
            max_tokens=Settings.CLAUDE_MAX_TOKENS,
            output_config=output_config,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            messages=[{"role": "user", "content": content}],
        ) as stream:
            message = stream.get_final_message()

        # Before any check below: a refused or truncated
        # call was still billed.
        usage_ledger.record(
            usage_ledger.Usage(
                role=self.role,
                model=message.model,
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
                cache_read_tokens=(
                    message.usage.cache_read_input_tokens or 0
                ),
                cache_write_tokens=(
                    message.usage.cache_creation_input_tokens
                    or 0
                ),
            )
        )

        text = "".join(
            block.text
            for block in message.content
            if block.type == "text"
        )

        if message.stop_reason == "refusal":
            raise RuntimeError(
                f"Claude model '{message.model}' declined "
                "the request"
                + (
                    f" ({message.stop_details.category})"
                    if message.stop_details
                    else ""
                )
            )

        if message.stop_reason == "max_tokens":
            # A cut-off file is worse than none: it reaches
            # the validator as a broken import, not as a
            # length problem.
            raise RuntimeError(
                f"Claude model '{self.model}' hit the token "
                "limit - raise Settings.CLAUDE_MAX_TOKENS"
            )

        if not text:
            raise RuntimeError(
                f"Claude model '{self.model}' returned an "
                f"empty response (stop_reason="
                f"{message.stop_reason})"
            )

        return text

    def generate_code(
        self,
        task: str,
    ) -> str:

        prompt = f"""
Create a complete TypeScript implementation.

Requirements:
- return valid TypeScript
- return code only
- no explanations

Task:
{task}
"""

        return strip_code_fences(
            self.generate_text(
                prompt
            )
        )
