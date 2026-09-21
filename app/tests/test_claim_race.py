import threading
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models.task import Task
from app.workers.claim import claim_next_task

def create_pending_task(db, task_type) -> int:
    row = db.execute(
        text("""
        INSERT INTO tasks (user_id, type, payload, status, priority, scheduled_at, max_runtime, attempts, max_attempts)
        VALUES (1, :type, '{}', 'pending', 0, now(), 300, 0, 3)
        RETURNING id
        """), {"type": task_type}
    ).fetchone()
    db.commit()
    return row[0]

def worker_try_claim_and_hold(results: list, index: int, barrier: threading.Barrier, task_type):
    db = SessionLocal()
    try:
        result = claim_next_task(db, allowed_types=[task_type])
        results[index] = result
        barrier.wait()
    except Exception as e:
        print(f"Thread {index} crashed: {e}")
    finally:
        db.close()

def test_only_one_worker_claims_task(db):
    task_id = None
    task_type = f"test_claim_race_{uuid.uuid4().hex[:8]}"
    try:
        num_workers = 10

        db.execute(text("""
                INSERT INTO task_type_limits (type, max_concurrent)
                VALUES (:type, :limit)
            """), {"type": task_type, "limit": num_workers})
        db.commit()

        task_id = create_pending_task(db, task_type)

        results = [None] * num_workers
        barrier = threading.Barrier(num_workers)
        threads = [
            threading.Thread(target=worker_try_claim_and_hold, args=(results, i, barrier, task_type))
            for i in range(num_workers)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        claimed = [r for r in results if r is not None]
        assert len(claimed) == 1, (
            f"Expected exactly 1 claim, got {len(claimed)}. "
            f"Results: {results}"
        )

        task, attempt_id = claimed[0]

        assert task.id == task_id
        assert task.status == "running"
        assert task.current_attempt_id == attempt_id
    finally:
        db.execute(text("DELETE FROM task_effects WHERE task_id = :id"), {"id": task_id})
        db.execute(text("DELETE FROM task_attempts WHERE task_id = :id"), {"id": task_id})
        db.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": task_id})
        db.execute(text("DELETE FROM task_type_limits WHERE type = :type"), {"type": task_type})
        db.commit()

def test_multiple_tasks_all_claimed(db):
    task_ids = []
    task_type = f"test_claim_race_{uuid.uuid4().hex[:8]}"
    try:
        num = 5

        db.execute(text("""
                INSERT INTO task_type_limits (type, max_concurrent)
                VALUES (:type, :limit)
            """), {"type": task_type, "limit": num})
        db.commit()

        task_ids = [create_pending_task(db, task_type) for _ in range(num)]

        results = [None] * num
        barrier = threading.Barrier(num)
        threads = [
            threading.Thread(target=worker_try_claim_and_hold, args=(results, i, barrier, task_type))
            for i in range(num)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        claimed = [r for r in results if r is not None]
        claimed_task_ids = [r[0].id for r in claimed]

        assert len(claimed) == num
        assert len(set(claimed_task_ids)) == num
    finally:
        for tid in task_ids:
        
            db.execute(text("DELETE FROM task_effects WHERE task_id = :id"), {"id": tid})
            db.execute(text("DELETE FROM task_attempts WHERE task_id = :id"), {"id": tid})
            db.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": tid})
        db.execute(text("DELETE FROM task_type_limits WHERE type = :type"), {"type": task_type})
        db.commit()