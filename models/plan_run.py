from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4


def now() -> str:

    return datetime.now(UTC).isoformat()


class RunStatus(str, Enum):
    """Where a background run of a plan stands."""

    # Written, the worker not yet up.
    QUEUED = "QUEUED"

    RUNNING = "RUNNING"

    # A human asked to stop; the worker finishes the task
    # in hand and stops before the next one.
    STOPPING = "STOPPING"

    # Nothing left that could run: done, or blocked.
    DONE = "DONE"

    STOPPED = "STOPPED"

    # A task failed; the run stops there, as run-all did.
    FAILED = "FAILED"

    # The worker died without saying so: killed, crashed,
    # or the machine went down. Found by its process being
    # gone, not by anything it wrote.
    INTERRUPTED = "INTERRUPTED"

    @property
    def active(self) -> bool:

        return self in (
            RunStatus.QUEUED,
            RunStatus.RUNNING,
            RunStatus.STOPPING,
        )


@dataclass
class PlanRun:
    """One background run of a plan, or of one of its tasks.

    The page no longer does the work; it reads this, which
    the worker process keeps current.
    """

    id: str = field(default_factory=lambda: str(uuid4()))

    plan_id: str = ""

    # 0 runs every task that becomes ready; otherwise only
    # this one.
    task_id: int = 0

    repository_path: str = ""

    status: RunStatus = RunStatus.QUEUED

    pid: int = 0

    # The plan task in hand, 0 between tasks.
    current_task: int = 0

    # Task records this run produced, in order.
    produced: list[str] = field(default_factory=list)

    message: str = ""

    started_at: str = field(default_factory=now)

    finished_at: str = ""

    @property
    def log_name(self) -> str:

        return f"run-{self.id}.log"
