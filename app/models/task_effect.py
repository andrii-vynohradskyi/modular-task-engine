from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey
from app.models.base import Base


class TaskEffect(Base):
    __tablename__ = "task_effects"

    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    effect_key = Column(String, primary_key=True)

    attempt_id = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
