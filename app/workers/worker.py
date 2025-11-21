import time
import os
import socket
import uuid
from datetime import datetime, timedelta, timezone

import signal
import sys

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, text

from app.database import SessionLocal
from app.models.task import Task
from app.models.task_attempt import TaskAttempt
from app.models.worker import Worker

from app.workers.context import TaskContext
from app.workers.modules import dummy, send_email, cleanup
from app.workers.claim import claim_next_task
from app.domain.state_machine import TaskStatus, InvalidTransition
from app.observability.logger import log

import threading

WORKER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:6]}"
POLL_INTERVAL = 2
shutdown_requested = False


def register_worker(db):
    worker = Worker(
        worker_id=WORKER_ID,
        hostname=socket.gethostname(),
        pid=os.getpid(),
        status="running",
        started_at=datetime.now(timezone.utc),
        last_heartbeat_at=datetime.now(timezone.utc)
    )
    db.merge(worker)
    db.commit()


def worker_heartbeat_loop():
    while True:
        db = SessionLocal()
        try:
            db.query(Worker).filter(
                Worker.worker_id == WORKER_ID
            ).update({
                "last_heartbeat_at": datetime.now(timezone.utc)
            })
            db.commit()
        finally:
            db.close()

        time.sleep(10)

def handle_shutdown(signum, frame):
    global shutdown_requested
    shutdown_requested = True
    db = SessionLocal()
    db.query(Worker).filter(
        Worker.worker_id == WORKER_ID
    ).update({
        "status": "stopping"
    })
    db.commit()
    db.close()
    log("worker_shutdown_signal_received", worker_id=WORKER_ID, signal=signum)


def recover_stuck_tasks(db: Session):
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(seconds=5)
    stuck_tasks = (
        db.query(Task)
        .filter(
            Task.status == TaskStatus.RUNNING,
            or_(
                Task.last_heartbeat_at < threshold,
                and_(
                    Task.last_heartbeat_at.is_(None),
                    text("started_at + (max_runtime || ' seconds')::interval < now()")
                )
            )
        )
        .all()
    )

    for task in stuck_tasks:
        ctx = TaskContext(task, db)
        try:
            ctx.worker_died()
            log(
                event="task_recovered",
                worker_id=WORKER_ID,
                task_id=task.id,
                attempt_id=task.current_attempt_id,
            )
        except (InvalidTransition, RuntimeError):
            pass


def execute_task(task: Task, ctx: TaskContext, db: Session):
    log(
        event="task_execution_started",
        worker_id=WORKER_ID,
        task_id=task.id,
        attempt_id=ctx.attempt_id,
        task_type=task.type,
    )

    try:
        if task.type == "dummy_sleep":
            result = dummy.run(ctx, task.payload)
        elif task.type == "send_email":
            result = send_email.run(ctx, task.payload)
        elif task.type == "cleanup":
            result = cleanup.run(ctx, task.payload)
        else:
            raise ValueError(f"Unknown task type: {task.type}")

        response = ctx.checkpoint()

        if response == "cancelled":
            ctx.cancel()
            log(
                event="task_cancelled",
                worker_id=WORKER_ID,
                task_id=task.id,
                attempt_id=ctx.attempt_id,
            )
            return

        if response == "timeout":
            ctx.error("timeout")
            log(
                event="task_timeout",
                worker_id=WORKER_ID,
                task_id=task.id,
                attempt_id=ctx.attempt_id,
            )
            return

        ctx.success(result)
        log(
            event="task_execution_finished",
            worker_id=WORKER_ID,
            task_id=task.id,
            attempt_id=ctx.attempt_id,
        )

    except RuntimeError as e:
        # fencing / zombie
        db.query(TaskAttempt).filter(
            TaskAttempt.attempt_id == ctx.attempt_id
        ).update({"status": "zombie"})
        db.commit()

        log(
            event="task_execution_zombie",
            worker_id=WORKER_ID,
            task_id=task.id,
            attempt_id=ctx.attempt_id,
            error=str(e),
        )
        return

    except Exception as e:
        try:
            ctx.error(str(e))
            log(
                event="task_execution_error",
                worker_id=WORKER_ID,
                task_id=task.id,
                attempt_id=ctx.attempt_id,
                error=str(e),
            )
        except (RuntimeError, InvalidTransition):
            # lost race
            pass


def main():
    log("worker_started", worker_id=WORKER_ID)

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    db = SessionLocal()
    register_worker(db)
    db.close()

    heartbeat_thread = threading.Thread(
        target=worker_heartbeat_loop,
        daemon=True
    )
    heartbeat_thread.start()

    while not shutdown_requested:
        db = SessionLocal()
        try:
            if shutdown_requested:
                break

            result = claim_next_task(db)

            if result:
                task, attempt_id = result
                ctx = TaskContext(task, db, attempt_id)
                execute_task(task, ctx, db)
            else:
                time.sleep(POLL_INTERVAL)

        except Exception as e:
            log("worker_loop_error", worker_id=WORKER_ID, error=str(e))

        finally:
            db.close()

    log("worker_shutdown_complete", worker_id=WORKER_ID)
    db = SessionLocal()
    db.query(Worker).filter(
        Worker.worker_id == WORKER_ID
    ).update({
        "status": "stopped"
    })
    db.commit()
    db.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
