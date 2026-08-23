from sqlalchemy import text
from app.database import SessionLocal
from app.core.security import hash_password
from app.core.config import settings

db = SessionLocal()

# Rate limits
db.execute(text("""
    INSERT INTO rate_limits (type, tokens, max_tokens, tokens_per_second, last_refill_at)
    VALUES 
        ('send_email', 10, 10, 0.5, now()),
        ('dummy_sleep', 100, 100, 10, now())
    ON CONFLICT (type) DO NOTHING
"""))

# Concurrency limits
db.execute(text("""
    INSERT INTO task_type_limits (type, max_concurrent)
    VALUES
        ('dummy_sleep', 3),
        ('send_email', 5),
        ('cleanup', 1)
    ON CONFLICT (type) DO NOTHING
"""))

# First cleanup task
db.execute(text("""
    INSERT INTO tasks (user_id, type, payload, status, priority, scheduled_at, max_runtime, attempts, max_attempts)
    VALUES (1, 'cleanup', '{"older_than_days": 7, "next_run_in_hours": 24}', 'pending', 0, now(), 300, 0, 3)
"""))

# Add admin user
password = hash_password(settings.ADMIN_PASSWORD)
db.execute(text("""
    INSERT INTO users (id, username, email, is_admin, hashed_password)
    VALUES (1, :username, :email, :is_admin, :password)
    ON CONFLICT (id) DO NOTHING
"""), {"username": "admin", "password": password, "email": "admin@gmail.com", "is_admin": True})

db.commit()
db.close()
print("Seeded successfully")