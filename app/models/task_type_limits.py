from sqlalchemy import Column, Integer, String, UniqueConstraint
from app.models.base import Base

class TaskTypeLimit(Base):
    __tablename__ = "task_type_limits"

    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False, unique=True)
    max_concurrent = Column(Integer, nullable=False)