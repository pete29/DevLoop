"""Where DevLoop's code is, and where it keeps its data.

Run from source, both are the project folder, as they always
were. Built into an exe, the code is unpacked to a temporary
folder on every start, so the data -- the database, .env and
the run logs -- lives in %LOCALAPPDATA%\\DevLoop instead.
DEVLOOP_HOME overrides both.
"""

import os
import sys

# The code: the project folder, or where the exe unpacked it.
ROOT = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_FOLDER_NAME = "DevLoop"


def frozen() -> bool:
    """Whether this is the built exe rather than the source."""

    return bool(getattr(sys, "frozen", False))


def home() -> str:
    """The folder that holds the database, .env and run logs."""

    chosen = (os.getenv("DEVLOOP_HOME") or "").strip()

    if chosen:
        return chosen

    if frozen():
        base = os.getenv("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, DATA_FOLDER_NAME)

    return ROOT


def env_path() -> str:

    return os.path.join(home(), ".env")
