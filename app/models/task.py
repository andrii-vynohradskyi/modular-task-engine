from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.models.base import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)

    status = Column(String, default="pending", nullable=False)
    result = Column(JSON, nullable=True)
    last_error = Column(String, nullable=True)

    attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    current_attempt_id = Column(String, nullable=True)
    progress = Column(Integer, default=0)

    priority = Column(Integer, nullable=False, default=0)

    max_runtime = Column(Integer, default=300)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    last_heartbeat_at = Column(DateTime(timezone=True))
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))
