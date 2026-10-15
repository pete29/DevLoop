from dataclasses import dataclass, field
from enum import Enum


class Priority(str, Enum):
    HIGH = "HIGH"

    MEDIUM = "MEDIUM"

    LOW = "LOW"

    @classmethod
    def parse(
        cls,
        value: str,
    ) -> "Priority":

        try:
            return cls(str(value).upper())

        except ValueError:
            return cls.MEDIUM

    @property
    def rank(self) -> int:
        """Lower sorts first."""

        return {
            Priority.HIGH: 0,
            Priority.MEDIUM: 1,
            Priority.LOW: 2,
        }[self]


@dataclass
class TaskBreakdown:
    """One task the planner carved out of an epic."""

    id: int = 0

    title: str = ""

    description: str = ""

    priority: Priority = Priority.MEDIUM

    # The ids of the tasks this one needs first.
    dependencies: list[int] = field(default_factory=list)

    # Source files the planner says this task writes from
    # scratch, and existing ones it changes. Checked by
    # PlanValidator against the folder and the graph.
    creates: list[str] = field(default_factory=list)

    modifies: list[str] = field(default_factory=list)

    @property
    def prompt(self) -> str:
        """What the developer is asked to build.

        The file lists go with it: the developer plans its
        own files, and without them it could not tell a
        task that extends a module from one that starts a
        new one.
        """

        parts = [self.title.strip()]

        if self.description.strip():
            parts.append(self.description.strip())

        files = []

        if self.creates:
            files.append("Create: " + ", ".join(self.creates))

        if self.modifies:
            files.append("Modify: " + ", ".join(self.modifies))

        if files:
            parts.append("\n".join(files))

        return "\n\n".join(parts)
