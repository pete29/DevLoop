import os
from dataclasses import dataclass, field

from models.task import Task
from services.file_writer import FileWriter
from services.git_service import GitService


@dataclass
class Rollback:
    """What rejecting a task did to the folder."""

    removed: list[str] = field(default_factory=list)

    restored: list[str] = field(default_factory=list)

    # Changed, but neither created by the task nor known to
    # git: there is no earlier version to go back to.
    kept: list[str] = field(default_factory=list)


def roll_back(task: Task) -> Rollback:
    """Undoes a rejected task's files, and nothing else.

    Rejecting used to change only a status. The files
    stayed on disk, so the next task surveyed the rejected
    code as part of the project and built on it. On a
    plan's shared branch that is worse: the rejected code
    would be imported, compiled and committed with the next
    task.

    Named files only. A file the task created is deleted;
    a file git tracks is restored from git; anything else
    was there before and is left alone.
    """

    result = Rollback()

    root = task.repository_path

    if not root or not os.path.isdir(root):
        return result

    service = GitService(root)

    # Restoring a plan task's files on another branch
    # would restore that branch's versions instead.
    if task.branch and service.is_repository():

        current = service.current_branch()

        if current != task.branch:
            raise ValueError(
                f"The task was generated on {task.branch}, "
                f"but {current} is checked out. Switch back "
                "before rejecting, so the right files are "
                "restored."
            )

    paths = [item.path for item in task.generated_files]

    created = set(task.created_files)

    tracked = (
        service.tracked(paths)
        if service.is_repository()
        else set()
    )

    for path in paths:

        if path in created:

            target = FileWriter.resolve(root, path)

            if os.path.exists(target):
                os.remove(target)

            result.removed.append(path)

        elif path in tracked:
            result.restored.append(path)

        else:
            result.kept.append(path)

    service.restore(result.restored)

    return result
