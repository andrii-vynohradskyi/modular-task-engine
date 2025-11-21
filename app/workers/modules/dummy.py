import time
from app.workers.context import TaskContext

def run(ctx: TaskContext, payload: dict):
    seconds = payload.get("seconds", 1)

    for i in range(seconds):
        sig = ctx.checkpoint()
        if sig:
            return {"stopped": sig}
        progress = int(((i + 1) / seconds) * 100)
        ctx.set_progress(progress)
        key = f"email:{i}"
        if ctx.register_effect(key):
            time.sleep(1)  # simulate sending
        else:
            pass
    return {"message": f"Slept {seconds} seconds"}
