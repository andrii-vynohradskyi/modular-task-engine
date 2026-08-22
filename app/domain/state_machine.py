from enum import Enum


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskEvent(str, Enum):
    CLAIM = "claim"
    SUCCESS = "success"
    ERROR = "error"
    CANCEL = "cancel"
    WORKER_DIED = "worker_died"


class InvalidTransition(Exception):
    pass


class TaskStateMachine:
    def get_next_status(self, task, event: TaskEvent):
        key = (task.status, event)

        if key not in ALLOWED_TRANSITIONS:
            raise InvalidTransition(
                f"Invalid transition: {task.status} + {event}"
            )

        transition = ALLOWED_TRANSITIONS[key]

        if callable(transition):
            return transition(task)
        else:
            return transition


def on_worker_died(task):
    if task.attempts >= task.max_attempts:
        return TaskStatus.FAILED
    return TaskStatus.PENDING


ALLOWED_TRANSITIONS = {
    (TaskStatus.PENDING, TaskEvent.CLAIM): TaskStatus.RUNNING,
    (TaskStatus.PENDING, TaskEvent.CANCEL): TaskStatus.CANCELLED,

    (TaskStatus.RUNNING, TaskEvent.SUCCESS): TaskStatus.DONE,
    (TaskStatus.RUNNING, TaskEvent.ERROR): TaskStatus.FAILED,
    (TaskStatus.RUNNING, TaskEvent.CANCEL): TaskStatus.CANCELLED,
    (TaskStatus.RUNNING, TaskEvent.WORKER_DIED): on_worker_died,
}

STATE_MACHINE = TaskStateMachine()