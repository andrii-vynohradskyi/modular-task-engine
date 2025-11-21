from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.orm import declarative_base
from datetime import datetime, timezone
from app.models.base import Base

class Worker(Base):
    __tablename__ = "workers"

    worker_id = Column(String, primary_key=True)
    hostname = Column(String, nullable=False)
    pid = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="running")
    started_at = Column(DateTime(timezone=True), nullable=False)
    last_heartbeat_at = Column(DateTime(timezone=True), nullable=False)
