import pytest
from sqlalchemy import text

from app.database import SessionLocal

from app.workers.rate_limiter import acquire_token


def test_rate_limit_allows_then_blocks():
    db = SessionLocal()

    # Setup: 1 token available, very slow refill
    db.execute(text("""
        INSERT INTO rate_limits (type, tokens, max_tokens, tokens_per_second, last_refill_at)
        VALUES ('test_type', 1, 1, 0.001, now())
        ON CONFLICT (type) DO UPDATE SET
            tokens = 1,
            max_tokens = 1,
            tokens_per_second = 0.001,
            last_refill_at = now()
    """))
    db.commit()

    # First call should succeed — 1 token available
    result1 = acquire_token(db, "test_type")

    # Second call should fail — bucket empty, refill rate too slow
    result2 = acquire_token(db, "test_type")

    # Cleanup
    db.execute(text("DELETE FROM rate_limits WHERE type = 'test_type'"))
    db.commit()
    db.close()

    assert result1 == True
    assert result2 == False