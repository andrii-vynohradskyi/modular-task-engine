import json

from sqlalchemy import text, or_, and_
from app.models.task import Task
from app.domain.state_machine import TaskStatus, InvalidTransition
from datetime import datetime, timezone, timedelta
from app.workers.context import TaskContext
from app.observability.logger import log

def run(ctx: TaskContext, payload: dict):
    now = datetime.now(timezone.utc)
    heartbeat_timeout = payload.get("heartbeat_timeout", 30)
    heartbeat_deadline = now - timedelta(seconds=heartbeat_timeout)
    next_run_in_seconds = payload.get("next_run_in_seconds", 10)
    next_run_at = now + timedelta(seconds=next_run_in_seconds)


    ctx.db.execute(text("""
                INSERT INTO tasks (user_id, type, payload, status, priority, scheduled_at, max_runtime, attempts, max_attempts)
                VALUES (1, 'recovery', :payload, 'pending', 100, :next_run_at, 300, 0, 3)
            """), {
        "payload": json.dumps({"heartbeat_timeout": heartbeat_timeout, "next_run_in_seconds": next_run_in_seconds}),
        "next_run_at": next_run_at
    })
    ctx.db.commit()

    stuck_tasks = (
        ctx.db.query(Task)
        .filter(
            Task.status == TaskStatus.RUNNING,
            or_(
                and_(
                    Task.last_heartbeat_at.is_not(None),
                    Task.last_heartbeat_at < heartbeat_deadline,
                ),
                text(
                    "started_at + (max_runtime || ' seconds')::interval < now()"
                ),
            ),
        )
        .all()
    )

    for task in stuck_tasks:
        task_ctx = TaskContext(task, ctx.db, task.current_attempt_id)
        try:
            task_ctx.worker_died()
            log(
                event="task_recovered",
                task_id=task.id,
                attempt_id=task.current_attempt_id,
            )
        except (InvalidTransition, RuntimeError):
            log(
                event="task_recovery_skipped",
                task_id=task.id,
                attempt_id=task.current_attempt_id,
            )

