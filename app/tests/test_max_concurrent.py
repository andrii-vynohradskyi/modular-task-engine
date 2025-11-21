import threading
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models.task import Task
from app.workers.claim import claim_next_task


def create_pending_task(db) -> int:
    """Insert one pending task directly, return its id."""
    row = db.execute(
        text("""
        INSERT INTO tasks (user_id, type, payload, status, priority, scheduled_at, max_runtime, attempts, max_attempts)
        VALUES (1, 'dummy_sleep', '{}', 'pending', 0, now(), 300, 0, 3)
        RETURNING id
        """)
    ).fetchone()
    db.commit()
    return row[0]



def worker_try_claim_and_hold(results: list, index: int, barrier: threading.Barrier):
    """Claim a task, then wait at the barrier before releasing."""
    db = SessionLocal()
    try:
        result = claim_next_task(db)
        results[index] = result
        barrier.wait()  # all threads wait here together
    finally:
        db.close()


def test_concurrency_limit():
    NUM = 10
    LIMIT = 2

    db = SessionLocal()
    db.execute(text("""
        INSERT INTO task_type_limits (type, max_concurrent)
        VALUES ('dummy_sleep', :limit)
        ON CONFLICT (type) DO UPDATE SET max_concurrent = :limit
    """), {"limit": LIMIT})
    db.commit()
    task_ids = [create_pending_task(db) for _ in range(NUM)]
    db.close()

    results = [None] * NUM
    barrier = threading.Barrier(NUM)  # all threads pause at the same point

    threads = [
        threading.Thread(target=worker_try_claim_and_hold, args=(results, i, barrier))
        for i in range(NUM)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    claimed = [r for r in results if r is not None]

    # Cleanup
    db = SessionLocal()
    for tid in task_ids:
        db.execute(text("DELETE FROM task_effects WHERE task_id = :id"), {"id": tid})
        db.execute(text("DELETE FROM task_attempts WHERE task_id = :id"), {"id": tid})
        db.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": tid})
    db.commit()
    db.close()

    assert len(claimed) == LIMIT