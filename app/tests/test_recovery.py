import uuid

from sqlalchemy import text
from datetime import datetime, timezone, timedelta

from app.domain.state_machine import TaskStatus
from app.models import Task
from app.workers.context import TaskContext
from app.workers.modules import recovery

def test_recovery_marks_stuck_tasks_pending_and_reschedules_itself(db):
    try:
        now = datetime.now(timezone.utc)
        created_at = now - timedelta(seconds=60)
        last_heartbeat_at = now - timedelta(seconds=40)

        attempt_id_1 = str(uuid.uuid4())
        attempt_id_2 = str(uuid.uuid4())
        attempt_id_3 = str(uuid.uuid4())

        # Heartbeat is expired
        task1 = Task(
            user_id=1,
            type="dummy_sleep",
            payload="",
            status=TaskStatus.RUNNING,
            priority=100,
            current_attempt_id=attempt_id_1,
            created_at=created_at,
            last_heartbeat_at=last_heartbeat_at,
            max_runtime = 300,
            max_attempts=3,
            scheduled_at=now
        )
        db.add(task1)

        created_at = now - timedelta(seconds=400)
        last_heartbeat_at = now - timedelta(seconds=5)
        started_at = now - timedelta(seconds=400)

        # Heartbeat is ok, max_runtime exceeded
        task2 = Task(
            user_id=1,
            type="dummy_sleep",
            payload="",
            status=TaskStatus.RUNNING,
            priority=100,
            current_attempt_id=attempt_id_2,
            created_at=created_at,
            last_heartbeat_at=last_heartbeat_at,
            max_runtime=300,
            max_attempts=3,
            scheduled_at=now,
            started_at=started_at,
        )
        db.add(task2)

        created_at = now - timedelta(seconds=400)
        started_at = now - timedelta(seconds=400)

        # Heartbeat is not set, max_runtime exceeded
        task3 = Task(
            user_id=1,
            type="dummy_sleep",
            payload="",
            status=TaskStatus.RUNNING,
            priority=100,
            current_attempt_id=attempt_id_3,
            created_at=created_at,
            max_runtime=300,
            max_attempts=3,
            scheduled_at=now,
            started_at=started_at,
        )
        db.add(task3)
        db.commit()

        ctx = TaskContext(task=None, db=db, attempt_id=None)

        before_ids = {
            row.id for row in db.query(Task.id).filter(Task.type == "recovery")
        }

        recovery.run(ctx, {"heartbeat_timeout": 30, "next_run_in_seconds": 10})

        new_recovery = (
            db.query(Task)
            .filter(Task.type == "recovery", Task.id.notin_(before_ids))
            .first()
        )

        assert new_recovery is not None
        assert task1.status == TaskStatus.PENDING
        assert task2.status == TaskStatus.PENDING
        assert task3.status == TaskStatus.PENDING
    finally:
        for task in (task1, task2, task3):
            db.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": task.id})
        if new_recovery is not None:
            db.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": new_recovery.id})
        db.commit()