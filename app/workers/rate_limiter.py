from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timezone
from app.observability.logger import log

def acquire_token(db: Session, task_type: str) -> bool:
    row = db.execute(
        text("""
            SELECT tokens, max_tokens, tokens_per_second, last_refill_at
            FROM rate_limits
            WHERE type = :type
            FOR UPDATE
        """),
        {"type": task_type}
    ).fetchone()

    if not row:
        log("rate_limit_not_configured", task_type=task_type)
        return True  # no rate limit configured, allow

    tokens, max_tokens, tokens_per_second, last_refill_at = row

    elapsed = (datetime.now(timezone.utc) - last_refill_at).total_seconds()
    new_tokens = min(tokens + elapsed * tokens_per_second, max_tokens)

    if new_tokens >= 1:
        db.execute(
            text("""
                UPDATE rate_limits
                SET
                    tokens = :tokens,
                    last_refill_at = now()
                WHERE type = :type
            """),
            {"tokens": new_tokens - 1, "type": task_type}
        )
        db.commit()
        return True

    db.rollback()
    return False