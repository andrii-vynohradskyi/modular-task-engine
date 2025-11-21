from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone

from app.api.dependencies import get_db
from app.models.task import Task
from app.schemas.admin import QueueTaskRead, ZombieRead, StatsRead

from app.models.worker import Worker

HEARTBEAT_TIMEOUT = 30
router = APIRouter()

@router.get("/queue", response_model=list[QueueTaskRead])
def get_queue(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    return (
        db.query(Task)
        .filter(
            Task.status == "pending",
            Task.scheduled_at <= now,
        )
        .order_by(
            Task.priority.desc(),
            Task.scheduled_at,
            Task.created_at,
        )
        .limit(100)
        .all()
    )

@router.get("/zombies", response_model=list[ZombieRead])
def get_zombies(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)

    rows = (
        db.query(Task)
        .filter(
            Task.status == "running",
            Task.last_heartbeat_at.isnot(None),
            Task.last_heartbeat_at < now - timedelta(seconds=1),
        )
        .all()
    )

    result = []

    for t in rows:
        result.append({
            "task_id": t.id,
            "attempt_id": t.current_attempt_id,
            "last_heartbeat_at": t.last_heartbeat_at,
            "seconds_dead": int((now - t.last_heartbeat_at).total_seconds()),
        })

    return result


@router.get("/stats", response_model=StatsRead)
def get_stats(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    zombie_threshold = now - timedelta(seconds=30)

    pending = db.query(Task).filter(Task.status == "pending").count()
    running = db.query(Task).filter(Task.status == "running").count()
    done = db.query(Task).filter(Task.status == "done").count()
    failed = db.query(Task).filter(Task.status == "failed").count()

    zombies = (
        db.query(Task)
        .filter(
            Task.status == "running",
            Task.last_heartbeat_at < zombie_threshold,
        )
        .count()
    )

    return {
        "pending": pending,
        "running": running,
        "done": done,
        "failed": failed,
        "zombies": zombies,
    }


@router.get("/workers/dashboard")
def workers_dashboard(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    workers = db.query(Worker).all()

    result = []
    running = 0
    dead = 0

    for w in workers:
        if w.last_heartbeat_at and \
           (now - w.last_heartbeat_at).total_seconds() <= HEARTBEAT_TIMEOUT:
            status = "running"
            running += 1
        else:
            status = "dead"
            dead += 1

        uptime = None
        if w.started_at:
            uptime = (now - w.started_at).total_seconds()

        result.append({
            "worker_id": w.worker_id,
            "hostname": w.hostname,
            "pid": w.pid,
            "started_at": w.started_at,
            "last_heartbeat_at": w.last_heartbeat_at,
            "status": status,
            "uptime_seconds": uptime
        })

    return {
        "cluster": {
            "total": len(workers),
            "running": running,
            "dead": dead
        },
        "workers": result
    }


