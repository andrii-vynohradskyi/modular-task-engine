from app.workers.context import TaskContext
from sqlalchemy import text


def run(ctx: TaskContext, payload: dict):
    older_than_days = payload.get("older_than_days", 7)
    next_run_in_hours = payload.get("next_run_in_hours", 24)

    ctx.db.execute(text("""
        DELETE FROM tasks 
        WHERE status IN ('done', 'failed', 'cancelled')
        AND finished_at < now() - interval '1 day' * :days
    """), {"days": older_than_days})

    ctx.db.execute(text("""
        DELETE FROM workers
        WHERE status = 'stopped'
        OR last_heartbeat_at < now() - interval '1 hour'
    """))

    ctx.db.execute(text("""
        INSERT INTO tasks (user_id, type, payload, status, priority, scheduled_at, max_runtime, attempts, max_attempts)
        VALUES (1, 'cleanup', :payload, 'pending', 0, now() + interval '1 hour' * :hours, 300, 0, 3)
    """), {
        "payload": '{"older_than_days": 7, "next_run_in_hours": 24}',
        "hours": next_run_in_hours
    })

    ctx.db.commit()

    return {"cleaned": True}