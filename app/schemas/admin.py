from pydantic import BaseModel
from datetime import datetime

class QueueTaskRead(BaseModel):
    id: int
    type: str
    status: str
    priority: int
    scheduled_at: datetime
    attempts: int
    created_at: datetime

    class Config:
        from_attributes = True

class ZombieRead(BaseModel):
    task_id: int
    attempt_id: str
    last_heartbeat_at: datetime
    seconds_dead: int

    class Config:
        from_attributes = True

class StatsRead(BaseModel):
    pending: int
    running: int
    done: int
    failed: int
    zombies: int


