from enum import Enum


class TaskStatus(str, Enum):
    NEW = "NEW"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    # Sent back by a human with notes; a newer record
    # holds the revision, on the same files.
    REVISED = "REVISED"
