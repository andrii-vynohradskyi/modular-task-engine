from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime


class TaskCreate(BaseModel):
    type: str
    payload: dict
    max_runtime: int
    scheduled_at: Optional[datetime] = None

class TaskRead(BaseModel):
    id: int
    user_id: int
    type: str
    payload: dict
    status: str
    result: Optional[Any]
    created_at: datetime
    progress: int

    class Config:
        from_attributes = True

class TaskAttemptRead(BaseModel):
    attempt_id: str
    started_at: datetime
    finished_at: Optional[datetime]
    status: str
    error: Optional[str]

    class Config:
        from_attributes = True
