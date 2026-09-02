import conftest
from app.models import Task
from datetime import datetime, timezone
import uuid
from app.workers.context import TaskContext
from app.domain.state_machine import TaskStatus
from sqlalchemy import text

def test_error_makes_status_failed(db):
    try:
        attempt_id = str(uuid.uuid4())
        task = Task(
            user_id=1,
            type="cleanup",
            payload="",
            status=TaskStatus.RUNNING,
            priority=10,
            current_attempt_id=attempt_id,
            scheduled_at=datetime.now(timezone.utc),
            max_attempts=0,
        )
        db.add(task)
        db.commit()

        ctx = TaskContext(task, db, attempt_id)

        ctx.error("")

        assert task.status == TaskStatus.FAILED
    finally:
        db.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": task.id})
        db.commit()

def test_error_makes_status_pending(db):
    try:
        attempt_id = str(uuid.uuid4())
        task = Task(
            user_id=1,
            type="cleanup",
            status=TaskStatus.RUNNING,
            payload="",
            priority=10,
            current_attempt_id = attempt_id,
            scheduled_at=datetime.now(timezone.utc),
            max_attempts=3,
        )
        db.add(task)
        db.commit()

        ctx = TaskContext(task, db, attempt_id)

        ctx.error("")

        assert task.status == TaskStatus.PENDING
    finally:
        db.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": task.id})
        db.commit()

def test_worker_died_makes_status_failed(db):
    try:
        attempt_id = str(uuid.uuid4())
        task = Task(
            user_id=1,
            type="cleanup",
            status=TaskStatus.RUNNING,
            payload="",
            priority=10,
            current_attempt_id = attempt_id,
            scheduled_at=datetime.now(timezone.utc),
            max_attempts=0,
        )
        db.add(task)
        db.commit()

        ctx = TaskContext(task, db, attempt_id)

        ctx.worker_died()

        assert task.status == TaskStatus.FAILED
    finally:
        db.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": task.id})
        db.commit()

def test_worker_died_makes_status_pending(db):
    try:
        attempt_id = str(uuid.uuid4())
        task = Task(
            user_id=1,
            type="cleanup",
            status=TaskStatus.RUNNING,
            payload="",
            priority=10,
            current_attempt_id = attempt_id,
            scheduled_at=datetime.now(timezone.utc),
            max_attempts=3,
        )
        db.add(task)
        db.commit()

        ctx = TaskContext(task, db, attempt_id)

        ctx.worker_died()

        assert task.status == TaskStatus.PENDING
    finally:
        db.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": task.id})
        db.commit()