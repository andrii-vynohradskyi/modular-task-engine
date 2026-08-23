from fastapi import APIRouter, Depends
from app.api.v1.routes import hello, users, auth, tasks, admin

from app.api.dependencies import require_admin

api_router = APIRouter()

api_router.include_router(hello.router, prefix="/hello", tags=["hello"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])