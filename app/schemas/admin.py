from pydantic import BaseModel, ConfigDict
from datetime import datetime

class QueueTaskRead(BaseModel):
    id: int
    type: str
    status: str
    priority: int
    scheduled_at: datetime
    attempts: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ZombieRead(BaseModel):
    task_id: int
    attempt_id: str
    last_heartbeat_at: datetime
    seconds_dead: int

    model_config = ConfigDict(from_attributes=True)

class StatsRead(BaseModel):
    pending: int
    running: int
    done: int
    failed: int
    zombies: int


