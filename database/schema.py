"""The database's schema, and the migrations that bring a file up to it.

Each repository class used to create its own table and,
for columns added later, compare the table against a list
and add what was missing. That could only ever add a
column; nothing recorded what state a file was in; and an
upgrade that failed halfway left it in between.

Now there is one numbered list. A database records the
number it has reached (SQLite's user_version); opening it
runs every later migration once, in order, each in its own
transaction, after copying the file aside. To change the
schema, append a migration -- never edit one that has
shipped, since databases out there have already run it.
"""

import os
import shutil
import sqlite3
import threading

# The first migration builds the schema as it stood when
# versioning began. Written so that it also completes any
# database made before then: every table is created if
# missing, and every column added if missing.
BASELINE = {
    "repositories": [
        ("id", "TEXT PRIMARY KEY"),
        ("name", "TEXT NOT NULL"),
        ("path", "TEXT NOT NULL"),
        ("created_at", "TEXT NOT NULL"),
    ],
    "requirements": [
        ("id", "TEXT PRIMARY KEY"),
        ("repository_id", "TEXT NOT NULL DEFAULT ''"),
        ("title", "TEXT NOT NULL DEFAULT ''"),
        ("content", "TEXT NOT NULL DEFAULT ''"),
        ("source", "TEXT NOT NULL DEFAULT 'MANUAL'"),
        ("issue", "TEXT NOT NULL DEFAULT '{}'"),
        ("created_at", "TEXT NOT NULL"),
        ("updated_at", "TEXT NOT NULL"),
    ],
    "plans": [
        ("id", "TEXT PRIMARY KEY"),
        ("repository_id", "TEXT NOT NULL DEFAULT ''"),
        ("requirement_id", "TEXT NOT NULL DEFAULT ''"),
        ("issue", "TEXT NOT NULL DEFAULT '{}'"),
        ("epic", "TEXT NOT NULL"),
        ("tasks", "TEXT NOT NULL DEFAULT '[]'"),
        ("completed", "TEXT NOT NULL DEFAULT '[]'"),
        ("executions", "TEXT NOT NULL DEFAULT '[]'"),
        ("issues", "TEXT NOT NULL DEFAULT '[]'"),
        ("created_at", "TEXT NOT NULL"),
        ("planning_cost", "REAL NOT NULL DEFAULT 0"),
        ("failed_cost", "REAL NOT NULL DEFAULT 0"),
        ("acted_comments", "TEXT NOT NULL DEFAULT '[]'"),
    ],
    "tasks": [
        ("id", "TEXT PRIMARY KEY"),
        ("repository_id", "TEXT NOT NULL DEFAULT ''"),
        ("repository_path", "TEXT NOT NULL DEFAULT ''"),
        ("issue", "TEXT NOT NULL DEFAULT '{}'"),
        ("description", "TEXT NOT NULL"),
        ("generated_code", "TEXT NOT NULL"),
        ("architecture_review", "TEXT NOT NULL"),
        ("architecture_score", "INTEGER NOT NULL"),
        ("generated_tests", "TEXT NOT NULL"),
        ("recommendation", "TEXT NOT NULL DEFAULT 'UNKNOWN'"),
        ("blockers", "TEXT NOT NULL DEFAULT '[]'"),
        ("warnings", "TEXT NOT NULL DEFAULT '[]'"),
        ("suggestions", "TEXT NOT NULL DEFAULT '[]'"),
        ("structural", "TEXT NOT NULL DEFAULT '[]'"),
        ("review_history", "TEXT NOT NULL DEFAULT '[]'"),
        ("review_iterations", "INTEGER NOT NULL DEFAULT 0"),
        ("generated_files", "TEXT NOT NULL DEFAULT '[]'"),
        ("git_operation", "TEXT NOT NULL DEFAULT '{}'"),
        ("git_push", "TEXT NOT NULL DEFAULT '{}'"),
        ("pull_request", "TEXT NOT NULL DEFAULT '{}'"),
        ("test_result", "TEXT NOT NULL DEFAULT '{}'"),
        ("diffs", "TEXT NOT NULL DEFAULT '[]'"),
        ("status", "TEXT NOT NULL"),
        ("created_at", "TEXT NOT NULL"),
        ("environment", "TEXT NOT NULL DEFAULT '[]'"),
        ("steps", "TEXT NOT NULL DEFAULT '[]'"),
        ("compile_result", "TEXT NOT NULL DEFAULT '{}'"),
        ("branch", "TEXT NOT NULL DEFAULT ''"),
        ("created_files", "TEXT NOT NULL DEFAULT '[]'"),
        ("cost", "REAL NOT NULL DEFAULT 0"),
        ("plan_id", "TEXT NOT NULL DEFAULT ''"),
        ("packages", "TEXT NOT NULL DEFAULT '[]'"),
    ],
    "plan_runs": [
        ("id", "TEXT PRIMARY KEY"),
        ("plan_id", "TEXT NOT NULL"),
        ("task_id", "INTEGER NOT NULL DEFAULT 0"),
        ("repository_path", "TEXT NOT NULL DEFAULT ''"),
        ("status", "TEXT NOT NULL"),
        ("pid", "INTEGER NOT NULL DEFAULT 0"),
        ("current_task", "INTEGER NOT NULL DEFAULT 0"),
        ("produced", "TEXT NOT NULL DEFAULT '[]'"),
        ("message", "TEXT NOT NULL DEFAULT ''"),
        ("started_at", "TEXT NOT NULL"),
        ("finished_at", "TEXT NOT NULL DEFAULT ''"),
    ],
    "preferences": [
        ("key", "TEXT PRIMARY KEY"),
        ("value", "TEXT NOT NULL DEFAULT ''"),
    ],
}


def columns_of(connection: sqlite3.Connection, table: str) -> set[str]:

    return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}


def add_missing_columns(connection: sqlite3.Connection, table: str, columns) -> None:
    """Adds each column the table lacks; a key column cannot be added later."""

    present = columns_of(connection, table)

    for name, definition in columns:

        if name not in present and "PRIMARY KEY" not in definition:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def baseline(connection: sqlite3.Connection) -> None:
    """1: the schema as it stood, completing any older database."""

    for table, columns in BASELINE.items():

        body = ",\n    ".join(f"{name} {definition}" for name, definition in columns)

        connection.execute(f"CREATE TABLE IF NOT EXISTS {table} (\n    {body}\n)")

        add_missing_columns(connection, table, columns)


def indexes(connection: sqlite3.Connection) -> None:
    """2: indexes for what every page load looks up."""

    connection.execute("CREATE INDEX IF NOT EXISTS tasks_by_plan ON tasks (plan_id)")
    connection.execute("CREATE INDEX IF NOT EXISTS tasks_by_branch ON tasks (branch)")
    connection.execute("CREATE INDEX IF NOT EXISTS runs_by_plan ON plan_runs (plan_id)")


# Append only. The position is the version: the first entry
# takes a database to version 1.
MIGRATIONS = [
    ("baseline", baseline),
    ("indexes", indexes),
]

LATEST = len(MIGRATIONS)

_lock = threading.Lock()


def version(connection: sqlite3.Connection) -> int:

    return connection.execute("PRAGMA user_version").fetchone()[0]


def backup_path(db_name: str, from_version: int) -> str:

    return f"{db_name}.v{from_version}.bak"


def migrate(db_name: str) -> int:
    """Brings a database file up to the latest version; returns it.

    The page and a background worker may open the file at
    the same moment, so the check and every migration run
    under an exclusive write lock: the second process waits,
    then finds nothing left to do.
    """

    with _lock:

        connection = sqlite3.connect(db_name, timeout=30, isolation_level=None)

        try:
            # The common case, one read: already up to date.
            if version(connection) >= LATEST:
                return version(connection)

            return upgrade(connection, db_name)

        finally:
            connection.close()


def upgrade(connection: sqlite3.Connection, db_name: str) -> int:

    connection.execute("BEGIN IMMEDIATE")

    current = version(connection)

    if current >= LATEST:
        connection.execute("COMMIT")
        return current

    has_data = bool(connection.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' LIMIT 1").fetchone())

    connection.execute("COMMIT")

    # A copy before anything changes, unless there is
    # nothing in the file yet to lose.
    if has_data and os.path.exists(db_name):
        shutil.copyfile(db_name, backup_path(db_name, current))

    for number, (name, step) in enumerate(MIGRATIONS, start=1):

        if number <= current:
            continue

        connection.execute("BEGIN IMMEDIATE")

        try:
            # Read again under the lock: another process may
            # have run this step since.
            if version(connection) >= number:
                connection.execute("COMMIT")
                continue

            step(connection)

            connection.execute(f"PRAGMA user_version = {number}")

            connection.execute("COMMIT")

        except Exception:
            connection.execute("ROLLBACK")
            raise

    return version(connection)
