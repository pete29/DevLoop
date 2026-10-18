"""Read-only access to the repository, for the model to ask for (#52).

The developer and QA answer in one call, shown what DevLoop
put in the prompt: the file under work and the files it
imports. A convention in a neighbouring test, or a helper two
imports away, they could not see, and guessed. These two tools
let them look, within limits:

- read only, inside the repository;
- never node_modules, .git or a .env file;
- a few calls per file written, so a task cannot wander.

The deterministic context stays: the tools are for what it
misses, not a replacement.
"""

import os

from config.settings import Settings

# Never shown, whatever the path: dependencies, history, keys.
REFUSED_FOLDERS = frozenset({"node_modules", ".git"})

MAX_READ_CHARS = 20_000

MAX_LISTED = 200

READ_FILE = {
    "name": "read_file",
    "description": (
        "Read one text file of the repository, by its path relative to the "
        "repository root, e.g. tests/parser.test.ts. For files the prompt did "
        "not show you: a neighbouring test's conventions, a helper further away."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Relative path, forward slashes."}},
        "required": ["path"],
        "additionalProperties": False,
    },
}

LIST_FILES = {
    "name": "list_files",
    "description": (
        "List the files under one folder of the repository, recursively, by "
        "relative path. Use '.' for the root."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"folder": {"type": "string", "description": "Relative folder, forward slashes."}},
        "required": ["folder"],
        "additionalProperties": False,
    },
}


def for_repository(root: str) -> "RepoTools | None":
    """Tools on `root`, or None when they are off or there is no folder."""

    if not Settings.REPO_TOOLS or not root or not os.path.isdir(root):
        return None

    return RepoTools(root)


class RepoTools:
    """read_file and list_files on one repository, with a call budget."""

    def __init__(self, root: str, budget: int | None = None) -> None:

        self.root = os.path.abspath(root)

        self.budget = Settings.REPO_TOOL_CALLS if budget is None else budget

        self.used = 0

        # What was asked for, in order: for the log and the tests.
        self.asked: list[str] = []

    @staticmethod
    def definitions() -> list[dict]:

        return [READ_FILE, LIST_FILES]

    @property
    def spent(self) -> bool:

        return self.used >= self.budget

    def rule(self) -> str:
        """What the prompt says about the tools."""

        return (
            "\nIf you need a repository file the prompt does not show -- a "
            "neighbouring test's conventions, a helper further away -- read it "
            f"with read_file or list_files: at most {self.budget} calls. Do not "
            "read files already shown above.\n"
        )

    def resolve(self, relative: str) -> str:
        """The absolute path, if it is inside the repository and allowed."""

        if not isinstance(relative, str) or not relative.strip():
            raise ValueError("a path is required")

        target = os.path.abspath(os.path.join(self.root, relative.strip().replace("\\", "/")))

        if os.path.commonpath([target, self.root]) != self.root:
            raise ValueError(f"{relative} is outside the repository")

        parts = os.path.relpath(target, self.root).replace("\\", "/").split("/")

        if any(part in REFUSED_FOLDERS for part in parts) or parts[-1].startswith(".env"):
            raise ValueError(f"{relative} is not readable here")

        return target

    def run(self, name: str, arguments: dict) -> tuple[str, bool]:
        """(result, is_error) for one call; the budget is counted here."""

        if self.spent:
            return ("No more reads: the budget for this file is spent. Write your answer now.", True)

        self.used += 1

        argument = (arguments or {}).get("path" if name == "read_file" else "folder", "")

        self.asked.append(f"{name}({argument})")

        try:
            if name == "read_file":
                return self.read(argument), False

            if name == "list_files":
                return self.list(argument), False

            return f"Unknown tool: {name}", True

        except (ValueError, OSError) as error:
            return f"Error: {error}", True

    def read(self, relative: str) -> str:

        target = self.resolve(relative)

        if not os.path.isfile(target):
            raise ValueError(f"{relative} does not exist")

        with open(target, encoding="utf-8", errors="replace") as handle:
            content = handle.read(MAX_READ_CHARS + 1)

        if len(content) > MAX_READ_CHARS:
            return content[:MAX_READ_CHARS] + "\n... (cut here: the file is longer)"

        return content

    def list(self, relative: str) -> str:

        target = self.resolve(relative or ".")

        if not os.path.isdir(target):
            raise ValueError(f"{relative} is not a folder")

        found = []

        for folder, folders, files in os.walk(target):

            folders[:] = sorted(name for name in folders if name not in REFUSED_FOLDERS and not name.startswith("."))

            for name in sorted(files):

                if name.startswith(".env"):
                    continue

                found.append(os.path.relpath(os.path.join(folder, name), self.root).replace("\\", "/"))

                if len(found) >= MAX_LISTED:
                    return "\n".join(found) + f"\n... (first {MAX_LISTED} only)"

        return "\n".join(found) or "(no files)"
