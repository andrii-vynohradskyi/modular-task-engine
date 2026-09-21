import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.observability.logger import log


def claim_next_task(
    db: Session, allowed_types: list[str] | None = None
) -> tuple[Task, str] | None:
    if allowed_types is not None and not allowed_types:
        return None

    type_filter = "AND t.type = ANY(:allowed_types)" if allowed_types else ""
    params = {"allowed_types": allowed_types} if allowed_types else {}

    # Candidate check only; capacity is revalidated after locking the type limit.
    candidate = db.execute(
        text(f"""
            SELECT t.id, t.type
            FROM tasks t
            WHERE t.status = 'pending'
              AND t.scheduled_at <= now()
              AND t.attempts < t.max_attempts
              {type_filter}
              AND (
                  SELECT COUNT(*) FROM tasks r
                  WHERE r.status = 'running' AND r.type = t.type
              ) < (
                  SELECT l.max_concurrent FROM task_type_limits l
                  WHERE l.type = t.type
              )
            ORDER BY t.priority DESC, t.scheduled_at ASC, t.created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        """),
        params,
    ).fetchone()

    if candidate is None:
        db.rollback()
        return None

    task_id, task_type = candidate

    # Workers claiming this type wait here in turn.
    # No SKIP LOCKED: skipping the only limit row means giving up.
    max_concurrent = db.execute(
        text("""
            SELECT max_concurrent FROM task_type_limits
            WHERE type = :type
            FOR UPDATE
        """),
        {"type": task_type},
    ).scalar()

    if max_concurrent is None:
        db.rollback()
        return None

    # New statement = fresh READ COMMITTED snapshot after the lock.
    running = db.execute(
        text("""
            SELECT COUNT(*) FROM tasks
            WHERE status = 'running' AND type = :type
        """),
        {"type": task_type},
    ).scalar()

    if running >= max_concurrent:
        db.rollback()
        return None

    # Candidate row is still locked, so no status guard is needed.
    attempt_id = str(uuid.uuid4())
    attempts = db.execute(
        text("""
            UPDATE tasks
            SET status = 'running',
                current_attempt_id = :attempt_id,
                started_at = now(),
                attempts = attempts + 1
            WHERE id = :id
            RETURNING attempts
        """),
        {"attempt_id": attempt_id, "id": task_id},
    ).scalar()

    db.add(
        TaskAttempt(
            task_id=task_id,
            attempt_id=attempt_id,
            started_at=datetime.now(timezone.utc),
            status="running",
        )
    )
    db.commit()

    task = db.get(Task, task_id)

    log("task_claimed", task_id=task_id, attempt_id=attempt_id, attempts=attempts)

    return task, attempt_id