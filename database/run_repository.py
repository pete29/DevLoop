import json
import sqlite3

from config.settings import Settings
from database import schema
from models.plan_run import PlanRun, RunStatus, now

COLUMNS = (
    "id",
    "plan_id",
    "task_id",
    "repository_path",
    "status",
    "pid",
    "current_task",
    "produced",
    "message",
    "started_at",
    "finished_at",
    "kind",
    "subject",
    "notes",
)


class RunRepository:
    """Background runs, shared by the page and the worker.

    Two processes write this database now, so each write is
    its own short transaction, and SQLite waits for a lock
    rather than failing at once.
    """

    def __init__(
        self,
        db_name: str = Settings.DATABASE_NAME,
    ) -> None:

        self.connection = sqlite3.connect(
            db_name,
            check_same_thread=False,
            timeout=30,
        )

        schema.migrate(db_name)


    def save(self, run: PlanRun) -> None:

        self.connection.execute(
            f"""
            INSERT OR REPLACE INTO plan_runs ({", ".join(COLUMNS)})
            VALUES ({", ".join("?" for _ in COLUMNS)})
            """,
            (
                run.id,
                run.plan_id,
                run.task_id,
                run.repository_path,
                run.status.value,
                run.pid,
                run.current_task,
                json.dumps(run.produced),
                run.message,
                run.started_at,
                run.finished_at,
                run.kind,
                run.subject,
                run.notes,
            ),
        )

        self.connection.commit()

    def latest_job(self, kind: str, subject: str) -> PlanRun | None:
        """The most recent run of a kind about one requirement or task."""

        row = self.connection.execute(
            f"""
            SELECT {", ".join(COLUMNS)} FROM plan_runs
            WHERE kind = ? AND subject = ?
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (kind, subject),
        ).fetchone()

        return self._parse(row) if row else None

    def get_by_id(self, run_id: str) -> PlanRun | None:

        row = self.connection.execute(
            f"SELECT {', '.join(COLUMNS)} FROM plan_runs WHERE id = ?",
            (run_id,),
        ).fetchone()

        return self._parse(row) if row else None

    def latest(self, plan_id: str) -> PlanRun | None:
        """The plan's most recent run, finished or not."""

        row = self.connection.execute(
            f"""
            SELECT {", ".join(COLUMNS)} FROM plan_runs
            WHERE plan_id = ?
            ORDER BY started_at DESC
            LIMIT 1
            """,
            (plan_id,),
        ).fetchone()

        return self._parse(row) if row else None

    def active(self) -> list[PlanRun]:

        rows = self.connection.execute(
            f"""
            SELECT {", ".join(COLUMNS)} FROM plan_runs
            WHERE status IN (?, ?, ?)
            """,
            tuple(
                status.value
                for status in RunStatus
                if status.active
            ),
        ).fetchall()

        return [self._parse(row) for row in rows]

    def request_stop(self, run_id: str) -> None:
        """Asks the worker to stop after the task in hand.

        Only an active run changes: a stop that arrives
        after the run ended must not reopen it.
        """

        self.connection.execute(
            """
            UPDATE plan_runs SET status = ?
            WHERE id = ? AND status IN (?, ?)
            """,
            (
                RunStatus.STOPPING.value,
                run_id,
                RunStatus.QUEUED.value,
                RunStatus.RUNNING.value,
            ),
        )

        self.connection.commit()

    def mark_started(self, run_id: str, pid: int) -> None:
        """QUEUED becomes RUNNING; a stop asked for already stays."""

        self.connection.execute(
            "UPDATE plan_runs SET pid = ? WHERE id = ?",
            (pid, run_id),
        )

        self.connection.execute(
            "UPDATE plan_runs SET status = ? WHERE id = ? AND status = ?",
            (RunStatus.RUNNING.value, run_id, RunStatus.QUEUED.value),
        )

        self.connection.commit()

    def progress(
        self,
        run_id: str,
        current_task: int,
        produced: list[str],
    ) -> None:
        """What the worker is on. Never the status: the page
        may have asked for a stop since the worker last read
        it, and a whole-row write would undo that."""

        self.connection.execute(
            """
            UPDATE plan_runs SET current_task = ?, produced = ?
            WHERE id = ?
            """,
            (current_task, json.dumps(produced), run_id),
        )

        self.connection.commit()

    def finish(
        self,
        run: PlanRun,
        status: RunStatus,
        message: str = "",
    ) -> None:

        run.status = status

        run.message = message

        run.current_task = 0

        run.finished_at = now()

        # The ending only: the worker's copy of the row is
        # older than what it wrote since (its pid, its
        # progress), and a whole-row save would undo that.
        self.connection.execute(
            """
            UPDATE plan_runs
            SET status = ?, message = ?, current_task = 0,
                finished_at = ?
            WHERE id = ?
            """,
            (status.value, message, run.finished_at, run.id),
        )

        self.connection.commit()

    def _parse(self, row) -> PlanRun:

        return PlanRun(
            id=row[0],
            plan_id=row[1],
            task_id=int(row[2] or 0),
            repository_path=row[3] or "",
            status=RunStatus(row[4]),
            pid=int(row[5] or 0),
            current_task=int(row[6] or 0),
            produced=json.loads(row[7] or "[]"),
            message=row[8] or "",
            started_at=row[9],
            finished_at=row[10] or "",
            kind=row[11] or "tasks",
            subject=row[12] or "",
            notes=row[13] or "",
        )
