"""Reading and writing the settings that live in .env.

The keys were set by editing a file by hand. Here they are
written one line at a time: every other line of .env --
comments, order, settings this does not know -- stays as it
was. A value is never shown back, only whether it is set,
how long it is and how it starts.
"""

import os
import re
from dataclasses import dataclass

from config.paths import env_path

# In the data folder: the project folder from source, beside
# the database in the exe (config/paths.py).
ENV_PATH = env_path()

NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")


@dataclass(frozen=True)
class Field:
    """One setting the page may write."""

    name: str

    secret: bool

    # Prefixes a value has to start with; empty for any.
    prefixes: tuple[str, ...] = ()

    number: bool = False


FIELDS = {
    field.name: field
    for field in (
        Field("ANTHROPIC_API_KEY", True, ("sk-ant-",)),
        Field("GITHUB_PAT", True, ("github_pat_", "ghp_")),
        Field("GITHUB_ADMIN_PAT", True, ("github_pat_", "ghp_")),
        Field("DEVLOOP_MONTH_LIMIT", False, number=True),
    )
}


class SettingError(ValueError):
    pass


def current(name: str) -> str:
    """The value in effect now: .env is loaded into the environment."""

    return (os.getenv(name) or "").strip()


def describe(name: str) -> str:
    """How a value is shown: never the value itself, for a secret.

    The start says which kind of key it is; the length is
    the first thing to check when GitHub answers 401.
    """

    value = current(name)

    if not value:
        return ""

    if not FIELDS[name].secret:
        return value

    start = next((prefix for prefix in FIELDS[name].prefixes if value.startswith(prefix)), value[:4])

    return f"{start}… ({len(value)})"


def check(name: str, value: str) -> str:
    """The value to store, cleaned, or SettingError saying why not."""

    if name not in FIELDS:
        raise SettingError(f"{name} cannot be set here.")

    field = FIELDS[name]

    value = value.strip()

    # One line, nothing .env would read as a quote, a
    # comment or a second setting.
    if any(character in value for character in "\r\n\"'#= \t"):
        raise SettingError("The value has a space, a quote, '#', '=' or a line break in it.")

    if not value:
        return ""

    if field.prefixes and not value.startswith(field.prefixes):
        raise SettingError(f"Expected a value starting with {' or '.join(field.prefixes)}.")

    if field.number:

        try:
            number = float(value)

        except ValueError:
            raise SettingError("Expected a number of dollars, such as 5 or 2.50.") from None

        if number < 0:
            raise SettingError("Expected 0 or more.")

    return value


def write(name: str, value: str, path: str | None = None) -> None:
    """Sets one line of .env, and the environment, to `value`.

    "" clears it. The file is written to a temporary name
    and swapped in, so a failure halfway leaves the old one.
    """

    if not NAME.match(name):
        raise SettingError(f"Not a setting name: {name}")

    path = path or ENV_PATH

    lines: list[str] = []

    if os.path.exists(path):
        with open(path, encoding="utf-8") as handle:
            lines = handle.read().splitlines()

    line = f"{name}={value}"

    pattern = re.compile(rf"^\s*{name}\s*=")

    replaced = False

    for index, existing in enumerate(lines):

        if pattern.match(existing):

            if not replaced:
                lines[index] = line
                replaced = True

            else:
                # A second definition would win when read; one only.
                lines[index] = None

    lines = [existing for existing in lines if existing is not None]

    if not replaced:
        lines.append(line)

    temporary = path + ".tmp"

    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")

    os.replace(temporary, path)

    if value:
        os.environ[name] = value

    else:
        os.environ.pop(name, None)


def save(name: str, value: str, path: str | None = None) -> str:
    """Checks, then writes. Returns the value stored."""

    cleaned = check(name, value)

    write(name, cleaned, path)

    return cleaned
