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


def test_only_one_worker_claims_task():
    NUM_WORKERS = 10

    # Setup: one pending task
    db = SessionLocal()
    task_id = create_pending_task(db)
    db.close()

    # All workers race simultaneously
    results = [None] * NUM_WORKERS
    barrier = threading.Barrier(NUM_WORKERS)
    threads = [
        threading.Thread(target=worker_try_claim_and_hold, args=(results, i, barrier))
        for i in range(NUM_WORKERS)
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one should have claimed
    claimed = [r for r in results if r is not None]
    assert len(claimed) == 1, (
        f"Expected exactly 1 claim, got {len(claimed)}. "
        f"Results: {results}"
    )

    task, attempt_id = claimed[0]

    # Cleanup
    db = SessionLocal()
    db.execute(text("DELETE FROM task_attempts WHERE task_id = :id"), {"id": task_id})
    db.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": task_id})
    db.commit()
    db.close()

    assert task.id == task_id
    assert task.status == "running"
    assert task.current_attempt_id == attempt_id


def test_multiple_tasks_all_claimed():
    """5 tasks, 5 workers — each task claimed exactly once."""
    NUM = 5

    db = SessionLocal()
    # Reset any leftover running tasks from previous test
    db.execute(text("UPDATE tasks SET status='pending' WHERE status='running' AND type='dummy_sleep'"))
    db.execute(text("""
        INSERT INTO task_type_limits (type, max_concurrent)
        VALUES ('dummy_sleep', :limit)
        ON CONFLICT (type) DO UPDATE SET max_concurrent = :limit
    """), {"limit": NUM})
    db.commit()
    task_ids = [create_pending_task(db) for _ in range(NUM)]
    db.close()

    results = [None] * NUM
    barrier = threading.Barrier(NUM)
    threads = [
        threading.Thread(target=worker_try_claim_and_hold, args=(results, i, barrier))
        for i in range(NUM)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    claimed = [r for r in results if r is not None]
    claimed_task_ids = [r[0].id for r in claimed]

    # Cleanup
    db = SessionLocal()
    for tid in task_ids:
        db.execute(text("DELETE FROM task_attempts WHERE task_id = :id"), {"id": tid})
        db.execute(text("DELETE FROM tasks WHERE id = :id"), {"id": tid})
    db.commit()
    db.close()

    assert len(claimed) == NUM
    assert len(set(claimed_task_ids)) == NUM