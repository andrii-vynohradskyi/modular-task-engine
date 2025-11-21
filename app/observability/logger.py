import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger("task_engine")
logger.setLevel(logging.INFO)

handler = logging.StreamHandler()
logger.addHandler(handler)


def log(event: str, level: str = "info", **fields):
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **fields,
    }

    try:
        line = json.dumps(record, default=str)
    except Exception:
        line = json.dumps({"event": event, "error": "log_serialization_failed"})

    getattr(logger, level, logger.info)(line)