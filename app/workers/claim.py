import uuid
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.observability.logger import log
from datetime import datetime, timezone

def claim_next_task(db: Session) -> tuple[Task, str] | None:
    attempt_id = str(uuid.uuid4())

    row = db.execute(
        text("""
        UPDATE tasks
        SET
            status = 'running',
            current_attempt_id = :attempt_id,
            started_at = now(),
            attempts = attempts + 1
        WHERE id = (
            SELECT id FROM tasks t
            WHERE t.status = 'pending'
                AND t.scheduled_at <= now()
                AND t.attempts < t.max_attempts
                AND EXISTS (
                    SELECT 1 FROM task_type_limits WHERE type = t.type
                    FOR UPDATE SKIP LOCKED
                )
                AND (
                    SELECT COUNT(*) FROM tasks running
                    WHERE running.status = 'running' 
                    AND running.type = t.type
                ) < (
                    SELECT max_concurrent FROM task_type_limits 
                    WHERE type = t.type
                )
            ORDER BY priority DESC, scheduled_at ASC, created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        RETURNING id, attempts
        """),
        {"attempt_id": attempt_id}
    ).fetchone()

    if not row:
        db.rollback()
        return None

    task_id, attempts = row

    attempt = TaskAttempt(
        task_id=task_id,
        attempt_id=attempt_id,
        started_at=datetime.now(timezone.utc),
        status="running",
    )
    db.add(attempt)
    db.commit()

    task = db.get(Task, task_id)

    log("task_claimed",
        task_id=task_id,
        attempt_id=attempt_id,
        attempts=attempts,
    )

    return task, attempt_id