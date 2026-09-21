import smtplib
from email.message import EmailMessage
from time import sleep
from app.core.config import Settings

from app.workers.context import TaskContext
from ..rate_limiter import acquire_token

SMTP_HOST = Settings.SMTP_HOST
SMTP_PORT = Settings.SMTP_PORT
FROM_EMAIL = "noreply@taskengine.local"
RETRY_INTERVAL = 1

def run(ctx: TaskContext, payload: dict):
    to = payload["to"]
    subject = payload["subject"]
    body = payload["body"]
    count = payload.get("count", 1)

    for i in range(count):
        while not acquire_token(ctx.db, "send_email"):
            sig = ctx.checkpoint()
            if sig:
                return {"stopped": sig}
            sleep(RETRY_INTERVAL)

        effect_key = f"email:{i}"
        if ctx.register_effect(effect_key):
            msg = EmailMessage()
            msg["From"] = FROM_EMAIL
            msg["To"] = to
            msg["Subject"] = f"{subject} #{i}"
            msg.set_content(body.replace("{{i}}", str(i)))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
                smtp.send_message(msg)
        else:
            pass
        ctx.set_progress(int((i + 1) / count * 100))

    return {"sent": count}
