import threading
import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.workers.claim import claim_next_task


def create_pending_task(db, task_type) -> int:
    row = db.execute(
        text("""
        INSERT INTO tasks (user_id, type, payload, status, priority, scheduled_at, max_runtime, attempts, max_attempts)
        VALUES (1, :type, '{}', 'pending', 0, now(), 300, 0, 3)
        RETURNING id
        """), {'type': task_type}
    ).fetchone()
    db.commit()
    return row[0]

def worker_try_claim_and_hold(results: list, index: int, task_type):
    db = SessionLocal()
    try:
        result = claim_next_task(db, allowed_types=[task_type])
        results[index] = result
    finally:
        db.close()


def test_concurrency_limit(db):
    task_ids = []
    task_type = f"test_concurrency_{uuid.uuid4().hex[:8]}"
    try:
        num = 10
        limit = 2

        task_type = f"test_concurrency_{uuid.uuid4().hex[:8]}"

        db.execute(text("""
            INSERT INTO task_type_limits (type, max_concurrent)
            VALUES (:type, :limit)
        """), {"type": task_type, "limit": limit})
        db.commit()

        task_ids = [create_pending_task(db, task_type) for _ in range(num)]

        results = [None] * num

        threads = [
            threading.Thread(target=worker_try_claim_and_hold, args=(results, i, task_type))
            for i in range(num)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        claimed = [r for r in results if r is not None]
        claimed_task_ids = [r[0].id for r in claimed]
        assert len(claimed) == limit
        assert len(set(claimed_task_ids)) == limit
    finally:
        for tid in task_ids:
            db.execute(text("DELETE FROM task_effects WHERE task_id = :id"), {"id": tid})
            db.execute(text("DELETE FROM task_attempts WHERE task_id = :id"), {"id": tid})
            db.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": tid})
        db.execute(text("DELETE FROM task_type_limits WHERE type = :type"), {"type": task_type})
        db.commit()

