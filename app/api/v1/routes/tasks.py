from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.domain.task_policy import DEFAULT_PRIORITIES
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.schemas.task import TaskCreate, TaskRead, TaskAttemptRead
from app.api.dependencies import get_current_user
from app.models.user import User
from fastapi import HTTPException

from app.workers.context import TaskContext
from app.domain.state_machine import InvalidTransition

router = APIRouter()


@router.post("/", response_model=TaskRead)
def create_task(
    task_in: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if task_in.type not in DEFAULT_PRIORITIES:
        raise HTTPException(400, "Unknown task type")

    priority = DEFAULT_PRIORITIES[task_in.type]

    now = datetime.now(timezone.utc)
    if task_in.scheduled_at:
        if task_in.scheduled_at < now:
            raise HTTPException(
                status_code=400,
                detail="scheduled_at must be in the future"
            )
        scheduled_at = task_in.scheduled_at
    else:
        scheduled_at = now

    task = Task(
        user_id=current_user.id,
        type=task_in.type,
        payload=task_in.payload,
        max_runtime=task_in.max_runtime,
        status="pending",
        priority=priority,
        scheduled_at=scheduled_at,
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


@router.get("/{task_id}/attempts", response_model=list[TaskAttemptRead])
def get_task_attempts(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    attempts = (
        db.query(TaskAttempt)
        .filter(TaskAttempt.task_id == task_id)
        .order_by(TaskAttempt.started_at)
        .all()
    )

    return attempts


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id).first()

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not allowed")

    return task

@router.post("/{task_id}/cancel")
def cancel_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
):
    # 1. Load task owned by user
    task = (
        db.query(Task)
        .filter(Task.id == task_id, Task.user_id == current_user.id)
        .first()
    )

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    ctx = TaskContext(task, db)

    try:
        ctx.cancel()
    except InvalidTransition:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel task in status '{task.status}'"
        )

    return {
        "id": task.id,
        "status": task.status,
        "progress": task.progress,
    }