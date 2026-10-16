"""Offline checks for the schema and its migrations.

Throwaway database files only:

    python -m tests.schema_test
"""

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing

from database import schema

failures: list[str] = []


def check(label: str, actual: object, expected: object) -> None:

    if actual == expected:
        print(f"OK   {label}")
        return

    failures.append(label)

    print(f"FAIL {label}: {actual!r} != {expected!r}")


def columns(path: str, table: str) -> list[str]:

    with closing(sqlite3.connect(path)) as connection:
        return [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]


def tables(path: str) -> list[str]:

    with closing(sqlite3.connect(path)) as connection:
        return sorted(name for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'"))


def user_version(path: str) -> int:

    with closing(sqlite3.connect(path)) as connection:
        return connection.execute("PRAGMA user_version").fetchone()[0]


folder = tempfile.mkdtemp()

try:

    print("=" * 80)
    print("A NEW DATABASE")
    print("=" * 80)

    fresh = os.path.join(folder, "fresh.db")

    check("migrates to the latest version", schema.migrate(fresh), schema.LATEST)

    check(
        "with every table",
        tables(fresh),
        sorted(schema.BASELINE),
    )

    check(
        "every column of each, later migrations' after the first",
        all(
            columns(fresh, table)[: len(cols)] == [name for name, _ in cols]
            for table, cols in schema.BASELINE.items()
        )
        and columns(fresh, "plan_runs")[-3:] == [name for name, _ in schema.JOB_COLUMNS],
        True,
    )

    check("and no backup of an empty file", os.path.exists(schema.backup_path(fresh, 0)), False)

    print()
    print("=" * 80)
    print("A DATABASE FROM BEFORE VERSIONING")
    print("=" * 80)

    old = os.path.join(folder, "old.db")

    with closing(sqlite3.connect(old)) as connection:

        # tasks as first released, plans without its later columns
        connection.execute(
            """CREATE TABLE tasks (
                id TEXT PRIMARY KEY, description TEXT NOT NULL, generated_code TEXT NOT NULL,
                architecture_review TEXT NOT NULL, architecture_score INTEGER NOT NULL,
                generated_tests TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL)"""
        )

        connection.execute(
            "INSERT INTO tasks VALUES ('t1', 'Build it', 'code', 'fine', 90, 'tests', 'APPROVED', '2026-01-01')"
        )

        connection.execute("CREATE TABLE plans (id TEXT PRIMARY KEY, epic TEXT NOT NULL, created_at TEXT NOT NULL)")

        connection.commit()

    check("starts at version 0", user_version(old), 0)

    schema.migrate(old)

    check("is brought to the latest", user_version(old), schema.LATEST)

    check(
        "its tables gain every missing column",
        set(columns(old, "tasks")) >= {"cost", "plan_id", "packages", "branch", "steps"},
        True,
    )

    with closing(sqlite3.connect(old)) as connection:
        row = connection.execute("SELECT description, cost, packages FROM tasks WHERE id = 't1'").fetchone()

    check("its rows survive, new columns at their defaults", row, ("Build it", 0.0, "[]"))

    check("a copy was kept first", os.path.exists(schema.backup_path(old, 0)), True)

    check(
        "and the copy is the file as it was",
        "cost" in columns(schema.backup_path(old, 0), "tasks"),
        False,
    )

    print()
    print("=" * 80)
    print("A SECOND OPEN CHANGES NOTHING")
    print("=" * 80)

    os.remove(schema.backup_path(old, 0))

    schema.migrate(old)

    check("no work, no backup", os.path.exists(schema.backup_path(old, schema.LATEST)), False)

    print()
    print("=" * 80)
    print("A MIGRATION THAT FAILS LEAVES NOTHING HALF-DONE")
    print("=" * 80)

    def broken(connection):
        connection.execute("ALTER TABLE tasks ADD COLUMN half TEXT NOT NULL DEFAULT ''")
        raise RuntimeError("the step failed")

    schema.MIGRATIONS.append(("broken", broken))
    schema.LATEST = len(schema.MIGRATIONS)

    try:
        schema.migrate(old)
        failures.append("the failure is raised")
        print("FAIL the failure is raised")

    except RuntimeError:
        print("OK   the failure is raised")

    finally:
        schema.MIGRATIONS.pop()
        schema.LATEST = len(schema.MIGRATIONS)

    check("the version stays where it was", user_version(old), schema.LATEST)

    check("and its change was rolled back", "half" in columns(old, "tasks"), False)

    print()
    print("=" * 80)
    print("THE REPOSITORIES WORK ON IT")
    print("=" * 80)

    from database.plan_repository import PlanRepository
    from database.task_repository import TaskRepository
    from models.plan import Plan
    from models.task import Task

    TaskRepository(old).save(Task(id="t2", description="Another", cost=0.05, plan_id="p"))

    check("a task saved with every field", TaskRepository(old).get_by_id("t2").cost, 0.05)

    check("the old one reads back", TaskRepository(old).get_by_id("t1").description, "Build it")

    PlanRepository(old).save(Plan(id="p", epic="Epic", planning_cost=0.06))

    check("a plan too", PlanRepository(old).get_by_id("p").planning_cost, 0.06)

    print()
    print("=" * 80)
    print("TWO PROCESSES AT ONCE")
    print("=" * 80)

    shared = os.path.join(folder, "shared.db")

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    code = f"import sys; sys.path.insert(0, {root!r}); from database import schema; print(schema.migrate({shared!r}))"

    workers = [
        subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, text=True)
        for _ in range(3)
    ]

    results = [worker.communicate(timeout=60)[0].strip() for worker in workers]

    check("each ends at the latest version", results, [str(schema.LATEST)] * 3)

    check("and the file is whole", user_version(shared), schema.LATEST)

finally:
    shutil.rmtree(folder, ignore_errors=True)

print()
print("=" * 80)

if failures:
    print(f"FAILED: {len(failures)}")
    raise SystemExit(1)

print("ALL SCHEMA CHECKS PASSED")
print("=" * 80)
