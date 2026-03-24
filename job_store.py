"""SQLite persistence for jobs and Stripe webhook idempotency."""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("longlist.job_store")

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None
_path_override: str | None = None


def _database_path() -> str:
    if _path_override is not None:
        return _path_override
    from config import DATABASE_PATH

    return DATABASE_PATH


def _connection() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        path = Path(_database_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(path), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
    return _conn


def init_db(db_path: str | None = None) -> None:
    """
    Create tables. Pass db_path for tests; omit to use DATABASE_PATH from config.
    Changing path closes any existing connection.
    """
    global _conn, _path_override
    if _conn is not None:
        _conn.close()
        _conn = None
    _path_override = db_path
    with _lock:
        conn = _connection()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS stripe_sessions (
                session_id TEXT PRIMARY KEY,
                job_id TEXT,
                created_at TEXT NOT NULL
            );
            """
        )
        conn.commit()
    logger.info("Job store initialized at %s", _database_path())


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        row = _connection().execute(
            "SELECT data FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
    if not row:
        return None
    return json.loads(row["data"])


def put_job(job_id: str, data: dict[str, Any]) -> None:
    data = dict(data)
    data.setdefault("job_id", job_id)
    now = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(data, default=str)
    with _lock:
        _connection().execute(
            """
            INSERT INTO jobs (job_id, data, updated_at) VALUES (?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
            """,
            (job_id, payload, now),
        )
        _connection().commit()


def merge_job(job_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    current = get_job(job_id) or {}
    current.update(patch)
    put_job(job_id, current)
    return current


def list_job_ids() -> list[str]:
    with _lock:
        rows = _connection().execute(
            "SELECT job_id FROM jobs ORDER BY updated_at DESC"
        ).fetchall()
    return [r["job_id"] for r in rows]


def list_jobs_summary() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for jid in list_job_ids():
        j = get_job(jid)
        if j:
            out[jid] = {
                "status": j.get("status"),
                "sender": j.get("sender"),
                "total": j.get("total_companies"),
            }
    return out


def count_jobs() -> int:
    with _lock:
        row = _connection().execute("SELECT COUNT(*) AS c FROM jobs").fetchone()
    return int(row["c"]) if row else 0


def try_claim_stripe_session(session_id: str, job_id: str) -> bool:
    """
    Record this checkout session as being processed. Returns True if this is the first
    delivery (caller should run the pipeline); False if duplicate webhook.
    """
    if not session_id:
        logger.error("try_claim_stripe_session: empty session_id")
        return False
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        conn = _connection()
        try:
            conn.execute(
                "INSERT INTO stripe_sessions (session_id, job_id, created_at) VALUES (?, ?, ?)",
                (session_id, job_id or "", now),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            conn.rollback()
            logger.info("Duplicate Stripe webhook ignored for session %s", session_id)
            return False
