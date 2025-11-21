from datetime import datetime, timezone
import uuid

from sqlalchemy import update, text
from sqlalchemy.orm import Session

from app.models.task import Task
from app.domain.state_machine import STATE_MACHINE, TaskEvent, TaskStatus
from app.models.task_attempt import TaskAttempt
from datetime import timedelta

class TaskContext:
    def __init__(self, task: Task, db: Session, attempt_id: str):
        self.task = task
        self.db = db
        self.attempt_id = attempt_id

    def refresh(self):
        self.db.refresh(self.task)


    def _apply_event_atomic(self, event, extra_values=None):
        self.refresh()

        old_status = self.task.status
        new_status = STATE_MACHINE.get_next_status(self.task, event)

        values = {"status": new_status}

        if extra_values:
            values.update(extra_values)

        stmt = (
            update(Task)
            .where(Task.id == self.task.id)
            .where(Task.status == old_status)
            .where(Task.current_attempt_id == self.attempt_id)
            .values(**values)
        )

        result = self.db.execute(stmt)

        if result.rowcount == 0:
            self.db.rollback()
            raise RuntimeError("Lost race or not active attempt")

        self.db.commit()
        self.db.refresh(self.task)

    def success(self, result: dict):
        self._apply_event_atomic(
            TaskEvent.SUCCESS,
            extra_values={
                "result": result,
                "progress": 100,
                "finished_at": datetime.now(timezone.utc),
                "current_attempt_id": None,
            },
        )

        #log
        self.db.query(TaskAttempt).filter(
            TaskAttempt.attempt_id == self.attempt_id
        ).update(
            {
                "finished_at": datetime.now(timezone.utc),
                "status": "success",
            }
        )
        self.db.commit()

    def error(self, error: str):
        self._apply_event_atomic(
            TaskEvent.ERROR,
            extra_values={
                "last_error": error,
                "finished_at": datetime.now(timezone.utc),
                "current_attempt_id": None,
            },
        )

        backoff = min(60 * (2 ** (self.task.attempts - 1)), 3600)

        self.task.scheduled_at = datetime.now(timezone.utc) + timedelta(seconds=backoff)
        self.db.commit()

        #log
        self.db.query(TaskAttempt).filter(
            TaskAttempt.attempt_id == self.attempt_id
        ).update(
            {
                "finished_at": datetime.now(timezone.utc),
                "status": "error",
                "error": error,
            }
        )
        self.db.commit()

    def cancel(self):
        self._apply_event_atomic(
            TaskEvent.CANCEL,
            extra_values={
                "finished_at": datetime.now(timezone.utc),
                "current_attempt_id": None,
            },
        )

        # log
        self.db.query(TaskAttempt).filter(
            TaskAttempt.attempt_id == self.attempt_id
        ).update(
            {
                "finished_at": datetime.now(timezone.utc),
                "status": "cancel",
            }
        )
        self.db.commit()

    def worker_died(self):
        self.db.query(TaskAttempt).filter(
            TaskAttempt.attempt_id == self.attempt_id
        ).update({
            "finished_at": datetime.now(timezone.utc),
            "status": "zombie",
        })

        self._apply_event_atomic(
            TaskEvent.WORKER_DIED,
            extra_values={
                "current_attempt_id": None,
            },
        )

    def heartbeat(self):
        stmt = (
            update(Task)
            .where(Task.id == self.task.id)
            .where(Task.current_attempt_id == self.attempt_id)
            .values(last_heartbeat_at=datetime.now(timezone.utc))
        )

        result = self.db.execute(stmt)
        self.db.commit()

        if result.rowcount == 0:
            raise RuntimeError("Lost fencing token")

    def set_progress(self, value: int):
        value = max(0, min(100, value))

        stmt = (
            update(Task)
            .where(Task.id == self.task.id)
            .where(Task.current_attempt_id == self.attempt_id)
            .values(progress=value)
        )

        result = self.db.execute(stmt)
        self.db.commit()

        if result.rowcount == 0:
            raise RuntimeError("Lost fencing token")

    def is_cancelled(self) -> bool:
        self.refresh()
        return self.task.status == TaskStatus.CANCELLED

    def is_timed_out(self) -> bool:
        if not self.task.started_at:
            return False

        elapsed = (datetime.now(timezone.utc) - self.task.started_at).total_seconds()
        return elapsed > self.task.max_runtime

    def checkpoint(self):
        self.heartbeat()

        if self.is_cancelled():
            return "cancelled"

        if self.is_timed_out():
            return "timeout"

        return None

    def register_effect(self, key: str) -> bool:
        result = self.db.execute(
            text("""
            INSERT INTO task_effects(task_id, effect_key, attempt_id)
            VALUES (:task_id, :key, :attempt_id)
            ON CONFLICT(task_id, effect_key) DO NOTHING
            """),
            {
                "task_id": self.task.id,
                "key": key,
                "attempt_id": self.attempt_id,
            },
        )

        self.db.commit()
        return result.rowcount == 1
