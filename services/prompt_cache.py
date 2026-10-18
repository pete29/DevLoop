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


def ask(llm, cached: list[str], prompt: str, tools=None) -> str:
    """Calls the model with `cached` as a reusable prefix.

    A provider that cannot cache -- a local model, a test's
    fake -- gets the same text as one string, so what the
    model reads is the same either way.
    """

    blocks = [block for block in cached if block.strip()]

    # Repository tools where the model can call them (#52);
    # a provider that cannot gets the prompt as it was.
    with_tools = getattr(llm, "generate_with_tools", None)

    if tools is not None and with_tools is not None:
        return with_tools(blocks, prompt + tools.rule(), tools)

    generate = getattr(llm, "generate_cached", None)

    if generate is not None and blocks:
        return generate(blocks, prompt)

    return llm.generate_text("".join(blocks) + prompt)


def ask_json(llm, cached: list[str], prompt: str, schema: dict) -> dict | None:
    """The answer in `schema`'s shape, or None where unsupported.

    None tells the caller to ask in text and parse instead:
    a local model, or a test's fake, has no structured
    outputs.
    """

    generate = getattr(llm, "generate_json", None)

    if generate is None:
        return None

    return generate([block for block in cached if block.strip()], prompt, schema)
