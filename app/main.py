from fastapi import FastAPI
from app.api.v1.api_router import api_router
from app.database import engine
from app.models.base import Base
from app.models import user, refresh_token, task, task_effect, task_attempt, worker, task_type_limits, rate_limits

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Modular Task Engine",
    version="0.1.0"
)

app.include_router(api_router)