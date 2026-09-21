# Modular Task Engine

A distributed task queue written from scratch in Python, using PostgreSQL as the only coordination layer (no Redis, RabbitMQ or Celery). Any number of workers, on one machine or several, claim and run tasks through the database.

I built it to learn how a task queue handles the hard parts: two workers grabbing the same task, workers crashing in the middle of a task, retries that must not repeat side effects, and limits on concurrency and request rate.

## Architecture

```mermaid
flowchart LR
    Client([Client]) -->|HTTP| API[FastAPI]
    API --> DB[(PostgreSQL)]
    W1[Worker 1] --> DB
    W2[Worker 2] --> DB
    WN[Worker N] --> DB
    W1 -.->|SMTP| Mail[Mail server]
```

The API stores tasks in PostgreSQL. Workers poll the database, claim tasks, send heartbeats while running, and write results back. Workers share no memory with each other.

## Task lifecycle

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> running: claim
    pending --> cancelled: cancel
    running --> done: success
    running --> pending: error or worker died, attempts left
    running --> failed: error or worker died, no attempts left
    running --> cancelled: cancel
```

A task that errors or loses its worker goes back to `pending` with exponential backoff (capped at one hour) until `max_attempts` is reached. After that it stays `failed` until an admin looks at it.

## Why PostgreSQL

Postgres already has what a queue needs: row locks, `SKIP LOCKED`, transactions and unique constraints. Using it as the queue means one less system to deploy and keep consistent with the data. The cost is throughput, since a dedicated broker handles much higher volume.

## How it works

### Claiming a task

A claim is one transaction with four steps:

1. Select a pending task with `FOR UPDATE SKIP LOCKED`. Workers never wait for each other here: a locked row is skipped and the worker takes the next one.
2. Lock the concurrency limit row for that task type with `FOR UPDATE`. Workers claiming the same type wait here in turn.
3. Count running tasks of that type, in a new statement.
4. If the type is under its limit, mark the task `running` with a new attempt id.

Step 3 has to be a separate statement. My first version did the lock and the count in one query. Under PostgreSQL's default READ COMMITTED isolation, a statement reads a snapshot taken when it starts, so a worker that had waited for the lock still saw the running count from before the other workers committed. The concurrency test caught it: with a limit of 2, all 10 workers claimed a task. A new statement takes a fresh snapshot, so the count is correct.

Tests: 10 threads race for 1 task and exactly 1 claims it. 5 threads and 5 tasks: all claimed, no duplicates. A limit of 2 with 10 threads: exactly 2 claim.

### Fencing tokens

Every claim gets a new attempt id (a UUID), stored in `current_attempt_id`. Every later state change includes it:

```sql
UPDATE tasks SET status = :new_status
WHERE id = :id AND status = :old_status AND current_attempt_id = :attempt_id
```

If a worker is declared dead and its task goes to another worker, the attempt id changes. When the old worker comes back and tries to write a result, the update matches zero rows and is rejected.

### Retries and duplicate emails

A retry runs the task again from the start; there is no checkpointing. To avoid sending the same email twice, each email is recorded in `task_effects` under a unique `(task_id, effect_key)` before it is sent. On a retry the insert conflicts and that email is skipped.

This makes each email at-most-once: if a worker crashes after recording an email but before sending it, that email is lost rather than duplicated. For notifications I prefer that to duplicates. True exactly-once delivery would need the mail provider to accept an idempotency key.

### Crash recovery

Workers update a heartbeat while running a task. A recovery task finds running tasks whose heartbeat is older than 30 seconds, or that ran past `max_runtime`, and sends them through the same retry logic as errors.

Recovery is itself a task in the engine and reschedules itself every 10 seconds. It schedules its next run before doing any work, so a crash during recovery cannot stop the chain.

Tests: an expired heartbeat, a healthy heartbeat past `max_runtime`, and no heartbeat past `max_runtime` are all requeued, and the next recovery run is scheduled.

### Concurrency and rate limits

`task_type_limits` caps how many tasks of one type run at once (enforced during claiming, above). A type with no row cannot be claimed, so a missing config entry blocks the type instead of leaving it unlimited.

`rate_limits` is a token bucket per type, used by `send_email` before each email. Tokens are refilled from the elapsed time when a worker asks for one, so no background refill process is needed. `FOR UPDATE` on the bucket row serializes workers.

Tests: token available and not available, refill over time, refill capped at `max_tokens`, no config (allowed), and 10 threads on a bucket of 5 tokens where exactly 5 succeed.

### Other tests

Retry logic: an error or a dead worker returns the task to `pending` while attempts remain, and to `failed` after. Auth: admin endpoints return 401 without a token, 403 for regular users and 200 for admins. Registration rejects invalid input (422) and a duplicate username or email (409).

## Running it

Python 3.13, FastAPI, SQLAlchemy, PostgreSQL 16, Alembic, pytest, Docker.

```bash
git clone https://github.com/andrii-vynohradskyi/modular-task-engine.git
cd modular-task-engine

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` in the project root:

```
DATABASE_URL=postgresql+psycopg2://taskengine:taskengine@localhost:5432/taskengine
SECRET_KEY=<output of: openssl rand -hex 32>
ADMIN_PASSWORD=<choose one>
```

Start the database and the test mail server, apply migrations, and load the initial config:

```bash
docker compose up -d postgres mailhog
alembic upgrade head
python -m scripts.seed
```

Run the API and a worker in separate terminals:

```bash
uvicorn app.main:app --reload
python -m app.workers.worker
```

API docs are at `localhost:8000/docs` and captured emails at `localhost:8025`. Start more workers by running the worker command again.

Tests run against a real PostgreSQL database, because locking and race conditions can't be checked against a mock:

```bash
pytest -v
```

## API

| Method   | Endpoint                   | Access         |
|----------|----------------------------|----------------|
| `POST`   | `/users/`                  | Public         |
| `GET`    | `/users/{id}`              | Owner or admin |
| `PUT`    | `/users/{id}`              | Owner or admin |
| `DELETE` | `/users/{id}`              | Owner or admin |
| `POST`   | `/auth/login`              | Public         |
| `POST`   | `/auth/refresh`            | Refresh cookie |
| `POST`   | `/auth/logout`             | Authenticated  |
| `GET`    | `/auth/me`                 | Authenticated  |
| `POST`   | `/tasks/`                  | Authenticated  |
| `GET`    | `/tasks/`                  | Authenticated  |
| `GET`    | `/tasks/{id}`              | Owner          |
| `GET`    | `/tasks/{id}/attempts`     | Owner          |
| `POST`   | `/tasks/{id}/cancel`       | Owner          |
| `GET`    | `/admin/queue`             | Admin          |
| `GET`    | `/admin/zombies`           | Admin          |
| `GET`    | `/admin/stats`             | Admin          |
| `GET`    | `/admin/workers/dashboard` | Admin          |

Admin accounts are created by the seed script, not through the API.

## Project structure

```
app/
├── api/v1/routes/     HTTP endpoints
├── core/              config, JWT, password hashing
├── domain/            state machine and retry policy
├── models/            SQLAlchemy models
├── schemas/           Pydantic models
├── workers/
│   ├── claim.py       claiming logic
│   ├── context.py     heartbeat, progress, state transitions
│   ├── rate_limiter.py
│   ├── worker.py      main loop
│   └── modules/       one file per task type
├── observability/     JSON logging
└── tests/
alembic/versions/      migrations
scripts/seed.py        initial config data
```

## Status and limitations

Work in progress:

- CI with GitHub Actions
- Tests for fencing tokens and effect deduplication

Known limitations:

- Workers poll for tasks; `LISTEN`/`NOTIFY` would reduce latency
- No task dependencies
- A single tasks table; high volume would need partitioning
