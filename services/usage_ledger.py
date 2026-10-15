from dataclasses import dataclass

from config.settings import Settings

# What one million tokens cost, in dollars: input, output,
# cache read. Writing to the cache costs 1.25x input.
CACHE_WRITE_FACTOR = 1.25


@dataclass
class Usage:
    """One model call: who made it, and what it cost.

    Nobody could say what a task cost, so nobody could say
    which agent to make cheaper. The roadmap's lesson about
    time applies to money unchanged: measure where it goes
    before changing what spends it.
    """

    role: str = ""

    model: str = ""

    input_tokens: int = 0

    output_tokens: int = 0

    cache_read_tokens: int = 0

    cache_write_tokens: int = 0

    # A local model: tokens worth counting, but no bill.
    free: bool = False

    @property
    def cost(self) -> float | None:
        """Dollars, or None for a model with no price.

        None rather than 0: a local model really is free,
        but an unpriced paid one is not, and showing $0
        for it would be a claim nobody checked.
        """

        if self.free:
            return 0.0

        prices = Settings.CLAUDE_PRICES.get(self.model)

        if prices is None:
            return None

        per_input, per_output, per_cache_read = prices

        return (
            self.input_tokens * per_input
            + self.output_tokens * per_output
            + self.cache_read_tokens * per_cache_read
            + self.cache_write_tokens
            * per_input
            * CACHE_WRITE_FACTOR
        ) / 1_000_000


# Every call this process has made, in order. A run takes
# a mark when it starts and reads what came after it, so
# nothing has to thread a ledger through every agent.
LEDGER: list[Usage] = []


def record(usage: Usage) -> None:

    LEDGER.append(usage)

    print(
        f"USAGE: {usage.role or '-'} {usage.model} "
        f"in={usage.input_tokens} out={usage.output_tokens}"
        + (
            f" cache_read={usage.cache_read_tokens}"
            if usage.cache_read_tokens
            else ""
        )
        + (
            f" cache_write={usage.cache_write_tokens}"
            if usage.cache_write_tokens
            else ""
        )
        + (
            f" ${usage.cost:.4f}"
            if usage.cost is not None
            else ""
        )
    )


def mark() -> int:

    return len(LEDGER)


def since(position: int) -> list[Usage]:

    return LEDGER[position:]


def _tokens(count: int) -> str:

    if count < 1000:
        return str(count)

    return f"{count / 1000:.1f}k"


def describe(records: list[Usage]) -> str:
    """Per role, then the total: calls, tokens, dollars.

    Facts only, so it reads the same in either language:
    `architect 2× 18.4k->1.2k $0.10 · ... · total $0.31`.

    ASCII arrows and words: a Windows console in cp1250
    cannot print → or Σ, and the print would end the run.
    """

    if not records:
        return ""

    roles: dict[str, list[Usage]] = {}

    for item in records:
        roles.setdefault(item.role or "-", []).append(item)

    parts = [
        _line(role, items)
        for role, items in roles.items()
    ]

    total = _cost(records)

    parts.append(
        "total "
        + (f"${total:.2f}" if total is not None else "?")
    )

    return " · ".join(parts)


def _line(role: str, items: list[Usage]) -> str:

    read = sum(
        item.input_tokens
        + item.cache_read_tokens
        + item.cache_write_tokens
        for item in items
    )

    written = sum(item.output_tokens for item in items)

    cost = _cost(items)

    return (
        f"{role} {len(items)}× "
        f"{_tokens(read)}->{_tokens(written)}"
        + (f" ${cost:.2f}" if cost is not None else "")
    )


def dollars(items: list[Usage]) -> float:
    """What the calls cost, unpriced ones counted as 0.

    For adding up, where a sum is needed whatever happens;
    the per-task line still says "?" for an unpriced model.
    """

    return sum(item.cost or 0.0 for item in items)


def _cost(items: list[Usage]) -> float | None:

    costs = [item.cost for item in items]

    if any(cost is None for cost in costs):
        return None

    return sum(costs)
