"""Prompts in two parts: what repeats, and what does not.

A prompt used to be one string with the variable part
first, so no two calls shared a byte of prefix and nothing
could be cached. Agents now pass the parts that repeat --
an agent's fixed rules, a task's context -- separately and
first. Claude caches each such block; a cache read costs a
twentieth of an input token on Opus 5.5 and a tenth on
Sonnet 5.5.

A cache write costs 1.25x, so only text that is sent again
within five minutes earns its place here: the Architect's
rules (every task of a plan) and a task's context (every
file the Developer writes for it).
"""


def ask(llm, cached: list[str], prompt: str) -> str:
    """Calls the model with `cached` as a reusable prefix.

    A provider that cannot cache -- a local model, a test's
    fake -- gets the same text as one string, so what the
    model reads is the same either way.
    """

    blocks = [block for block in cached if block.strip()]

    generate = getattr(llm, "generate_cached", None)

    if generate is not None and blocks:
        return generate(blocks, prompt)

    return llm.generate_text("".join(blocks) + prompt)
