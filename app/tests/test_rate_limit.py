import pytest
from sqlalchemy import text

from app.database import SessionLocal
from app.models import RateLimit
from datetime import datetime, timezone, timedelta
from app.workers.rate_limiter import acquire_token

import threading

def test_acquire_token_true_when_there_is_token(db):
    try:
        rate_limit = RateLimit(
            type='test_type', tokens=1, max_tokens=1,
            last_refill_at=datetime.now(timezone.utc), tokens_per_second=0
        )
        db.add(rate_limit)
        db.commit()

        assert acquire_token(db, "test_type") == True
    finally:
        db.execute(text("DELETE FROM rate_limits WHERE id = :id"), {"id": rate_limit.id})
        db.commit()

def test_acquire_token_false_when_there_is_no_token(db):
    try:
        rate_limit = RateLimit(
            type='test_type', tokens=0, max_tokens=1,
            last_refill_at=datetime.now(timezone.utc), tokens_per_second=0
        )
        db.add(rate_limit)
        db.commit()

        assert acquire_token(db, "test_type") == False
    finally:
        db.execute(text("DELETE FROM rate_limits WHERE id = :id"), {"id": rate_limit.id})
        db.commit()


def test_bucket_refills_itself(db):
    try:
        last_refill_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        rate_limit = RateLimit(
            type='test_type', tokens=1, max_tokens=100,
            last_refill_at=last_refill_at, tokens_per_second=5
        )
        db.add(rate_limit)
        db.commit()

        acquire_token(db, "test_type")

        tokens = db.execute(
            text("""
                    SELECT tokens
                    FROM rate_limits
                    WHERE type = :type
                """),
            {"type": "test_type"}
        ).fetchone()
        assert 24.9 <= tokens[0] <= 25.1
    finally:
        db.execute(text("DELETE FROM rate_limits WHERE id = :id"), {"id": rate_limit.id})
        db.commit()


def test_acquire_token_allows_when_no_config_exists(db):
    before_ids = {
        row.id for row in db.query(RateLimit.id)
    }

    assert acquire_token(db, "test_type") == True

    new_rows = (
        db.query(RateLimit)
        .filter(RateLimit.id.notin_(before_ids))
        .first()
    )

    assert new_rows is None


def worker_try_acquire_token(results: list , index: int):
    db = SessionLocal()
    try:
        result = acquire_token(db, "test_type")
        results[index] = result
    finally:
        db.close()


def test_bucket_concurrency(db):
    try:
        last_refill_at = datetime.now(timezone.utc)
        rate_limit = RateLimit(
            type='test_type', tokens=5, max_tokens=10,
            last_refill_at=last_refill_at, tokens_per_second=0
        )
        db.add(rate_limit)
        db.commit()

        num_workers = 10
        results = [None] * num_workers
        threads = [
            threading.Thread(target=worker_try_acquire_token, args=(results, i))
            for i in range(num_workers)
        ]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert results.count(True) == 5
        assert results.count(False) == 5
    finally:
        db.execute(text("DELETE FROM rate_limits WHERE id = :id"), {"id": rate_limit.id})
        db.commit()