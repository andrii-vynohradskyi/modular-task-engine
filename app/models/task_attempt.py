from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from app.models.base import Base

class TaskAttempt(Base):
    __tablename__ = "task_attempts"

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)

    attempt_id = Column(String, nullable=False)

    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)

    status = Column(String, nullable=False)

    error = Column(String, nullable=True)
