from sqlalchemy import Column, Integer, Float, String, DateTime
from app.models.base import Base

class RateLimit(Base):
    __tablename__ = "rate_limits"

    id = Column(Integer, primary_key=True)
    type = Column(String, nullable=False, unique=True)
    tokens = Column(Float, nullable=False)
    max_tokens = Column(Float, nullable=False)
    last_refill_at = Column(DateTime(timezone=True), nullable=False)
    tokens_per_second = Column(Float, nullable=False)