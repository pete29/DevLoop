import json
import sqlite3

from config.settings import Settings
from models.github_issue import IssueLink
from models.plan import Plan
from models.task_breakdown import Priority, TaskBreakdown
from models.task_execution import (
    ExecutionStatus,
    TaskExecution,
)

COLUMNS = (
    "id",
    "repository_id",
    "requirement_id",
    "issue",
    "epic",
    "tasks",
    "completed",
    "executions",
    "issues",
    "created_at",
    "planning_cost",
    "failed_cost",
    "acted_comments",
)

COLUMN_LIST = ",\n                ".join(COLUMNS)

PLACEHOLDERS = ", ".join("?" for _ in COLUMNS)

# Columns added after the table first shipped, with the
# definition used to retrofit an existing database.
ADDED_COLUMNS = {
    "executions": "TEXT NOT NULL DEFAULT '[]'",
    "issues": "TEXT NOT NULL DEFAULT '[]'",
    "requirement_id": "TEXT NOT NULL DEFAULT ''",
    "issue": "TEXT NOT NULL DEFAULT '{}'",
    "planning_cost": "REAL NOT NULL DEFAULT 0",
    "failed_cost": "REAL NOT NULL DEFAULT 0",
    "acted_comments": "TEXT NOT NULL DEFAULT '[]'",
}


class PlanRepository:
    def __init__(
        self,
        db_name: str = Settings.DATABASE_NAME,
    ) -> None:
        # A background worker writes plans too.
        self.connection = sqlite3.connect(
            db_name,
            check_same_thread=False,
            timeout=30,
        )

        self.create_table()

    def create_table(self) -> None:
        cursor = self.connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS plans (
                id TEXT PRIMARY KEY,
                repository_id TEXT NOT NULL DEFAULT '',
                requirement_id TEXT NOT NULL DEFAULT '',
                issue TEXT NOT NULL DEFAULT '{}',
                epic TEXT NOT NULL,
                tasks TEXT NOT NULL DEFAULT '[]',
                completed TEXT NOT NULL DEFAULT '[]',
                executions TEXT NOT NULL DEFAULT '[]',
                issues TEXT NOT NULL DEFAULT '[]',
                created_at TEXT NOT NULL
            )
            """)

        self.connection.commit()

        self.migrate()

    def migrate(self) -> None:

        cursor = self.connection.cursor()

        columns = {
            row[1]
            for row in cursor.execute(
                "PRAGMA table_info(plans)"
            )
        }

        for name, definition in ADDED_COLUMNS.items():

            if name in columns:
                continue

            cursor.execute(
                f"ALTER TABLE plans ADD COLUMN "
                f"{name} {definition}"
            )

        self.connection.commit()

    def _tasks_json(self, plan: Plan) -> str:

        return json.dumps(
            [
                {
                    "id": item.id,
                    "title": item.title,
                    "description": item.description,
                    "priority": item.priority.value,
                    "dependencies": item.dependencies,
                    "creates": item.creates,
                    "modifies": item.modifies,
                }
                for item in plan.tasks
            ]
        )

    def _executions_json(self, plan: Plan) -> str:

        return json.dumps(
            [
                {
                    "task_id": item.task_id,
                    "status": item.status.value,
                    "started_at": item.started_at,
                    "completed_at": item.completed_at,
                    "error": item.error,
                    "task_record_id": item.task_record_id,
                }
                for item in plan.executions
            ]
        )

    def save(self, plan: Plan) -> None:

        cursor = self.connection.cursor()

        cursor.execute(
            f"""
            INSERT INTO plans (
                {COLUMN_LIST}
            )
            VALUES (
                {PLACEHOLDERS}
            )
            """,
            (
                plan.id,
                plan.repository_id,
                plan.requirement_id,
                json.dumps(
                    {
                        "id": plan.issue.id,
                        "number": plan.issue.number,
                        "title": plan.issue.title,
                        "state": plan.issue.state,
                        "url": plan.issue.url,
                    }
                ),
                plan.epic,
                self._tasks_json(plan),
                json.dumps(plan.completed),
                self._executions_json(plan),
                json.dumps(plan.issues),
                plan.created_at,
                plan.planning_cost,
                plan.failed_cost,
                json.dumps(plan.acted_comments),
            ),
        )

        self.connection.commit()

    def replace_tasks(self, plan: Plan) -> None:
        """Saves a plan's new task list, its problems and costs.

        Executions of tasks no longer in the plan go with
        them, so the dashboard counts only what is planned.
        """

        kept = {item.id for item in plan.tasks}

        plan.executions = [
            execution
            for execution in plan.executions
            if execution.task_id in kept
        ]

        self.connection.execute(
            """
            UPDATE plans
            SET tasks = ?, issues = ?, executions = ?, completed = ?,
                planning_cost = ?
            WHERE id = ?
            """,
            (
                self._tasks_json(plan),
                json.dumps(plan.issues),
                self._executions_json(plan),
                json.dumps(plan.completed),
                plan.planning_cost,
                plan.id,
            ),
        )

        self.connection.commit()

    def mark_acted(self, plan_id: str, keys: list[str]) -> list[str]:
        """Records review comments as sent back; returns them all."""

        row = self.connection.execute(
            "SELECT acted_comments FROM plans WHERE id = ?",
            (plan_id,),
        ).fetchone()

        acted = json.loads(row[0] or "[]") if row else []

        acted += [key for key in keys if key not in acted]

        self.connection.execute(
            "UPDATE plans SET acted_comments = ? WHERE id = ?",
            (json.dumps(acted), plan_id),
        )

        self.connection.commit()

        return acted

    def add_failed_cost(self, plan_id: str, dollars: float) -> None:
        """Adds what a failed attempt spent, in the database.

        An increment rather than a write of the plan's copy:
        the page and a worker may both hold the plan, and
        the later write would drop the other's addition.
        """

        self.connection.execute(
            "UPDATE plans SET failed_cost = failed_cost + ? WHERE id = ?",
            (dollars, plan_id),
        )

        self.connection.commit()

    def update_progress(self, plan: Plan) -> None:
        """Records what has been attempted and how it went."""

        cursor = self.connection.cursor()

        cursor.execute(
            """
            UPDATE plans
            SET executions = ?, completed = ?
            WHERE id = ?
            """,
            (
                self._executions_json(plan),
                json.dumps(plan.completed),
                plan.id,
            ),
        )

        self.connection.commit()

    def delete(self, plan_id: str) -> None:

        cursor = self.connection.cursor()

        cursor.execute(
            """
            DELETE FROM plans
            WHERE id = ?
            """,
            (plan_id,),
        )

        self.connection.commit()

    def _parse_tasks(
        self,
        tasks_json: str,
    ) -> list[TaskBreakdown]:

        return [
            TaskBreakdown(
                id=int(item.get("id") or 0),
                title=item.get("title", ""),
                description=item.get("description", ""),
                priority=Priority.parse(
                    item.get("priority", "")
                ),
                dependencies=[
                    int(value)
                    for value in item.get(
                        "dependencies", []
                    )
                ],
                # Absent from plans saved before tasks named
                # their files.
                creates=list(item.get("creates") or []),
                modifies=list(item.get("modifies") or []),
            )
            for item in json.loads(tasks_json or "[]")
        ]

    def _parse_executions(
        self,
        executions_json: str,
        completed_json: str,
    ) -> list[TaskExecution]:
        """Execution records, or a stand-in for old rows.

        Plans saved before executions existed only knew
        which tasks had finished, so those are turned into
        completed records rather than losing the progress.
        """

        records = json.loads(executions_json or "[]")

        if records:

            return [
                TaskExecution(
                    task_id=int(item.get("task_id") or 0),
                    status=ExecutionStatus.parse(
                        item.get("status", "")
                    ),
                    started_at=item.get("started_at", ""),
                    completed_at=item.get(
                        "completed_at", ""
                    ),
                    error=item.get("error", ""),
                    task_record_id=item.get(
                        "task_record_id", ""
                    ),
                )
                for item in records
            ]

        return [
            TaskExecution(
                task_id=int(task_id),
                status=ExecutionStatus.COMPLETED,
            )
            for task_id in json.loads(
                completed_json or "[]"
            )
        ]

    def _parse_issue(self, issue_json: str) -> IssueLink:
        data = json.loads(issue_json or "{}")

        return IssueLink(
            id=int(data.get("id") or 0),
            number=int(data.get("number") or 0),
            title=data.get("title", ""),
            state=data.get("state", ""),
            url=data.get("url", ""),
        )

    def _to_plan(self, row: tuple) -> Plan:

        return Plan(
            id=row[0],
            repository_id=row[1],
            requirement_id=row[2],
            issue=self._parse_issue(row[3]),
            epic=row[4],
            tasks=self._parse_tasks(row[5]),
            executions=self._parse_executions(
                row[7],
                row[6],
            ),
            issues=json.loads(row[8] or "[]"),
            created_at=row[9],
            planning_cost=float(row[10] or 0),
            failed_cost=float(row[11] or 0),
            acted_comments=json.loads(row[12] or "[]"),
        )

    def get_all(self) -> list[Plan]:

        cursor = self.connection.cursor()

        rows = cursor.execute(f"""
            SELECT
                {COLUMN_LIST}
            FROM plans
            ORDER BY created_at DESC
            """).fetchall()

        return [self._to_plan(row) for row in rows]

    def get_by_id(self, plan_id: str) -> Plan | None:

        cursor = self.connection.cursor()

        row = cursor.execute(
            f"""
            SELECT
                {COLUMN_LIST}
            FROM plans
            WHERE id = ?
            """,
            (plan_id,),
        ).fetchone()

        if row is None:
            return None

        return self._to_plan(row)
