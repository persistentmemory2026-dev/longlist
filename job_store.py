"""Job persistence — PostgreSQL (primary) with SQLite fallback for local dev."""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("longlist.job_store")

_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Detect backend: DATABASE_URL → PostgreSQL, else SQLite
# ---------------------------------------------------------------------------
_USE_PG = bool(os.getenv("DATABASE_URL"))
_pg_pool = None
_sqlite_conn = None
_sqlite_path_override: str | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# PostgreSQL helpers
# ---------------------------------------------------------------------------
def _get_pg():
    global _pg_pool
    if _pg_pool is None:
        import psycopg2
        from psycopg2 import pool as pg_pool
        _pg_pool = pg_pool.ThreadedConnectionPool(
            minconn=1, maxconn=5,
            dsn=os.environ["DATABASE_URL"],
        )
    return _pg_pool


def _pg_exec(sql: str, params: tuple = (), *, fetch: str = "none"):
    """Execute a query on PostgreSQL. fetch: 'none', 'one', 'all'."""
    pool = _get_pg()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if fetch == "one":
                result = cur.fetchone()
            elif fetch == "all":
                result = cur.fetchall()
            else:
                result = None
            conn.commit()
            return result
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ---------------------------------------------------------------------------
# SQLite helpers (local dev fallback)
# ---------------------------------------------------------------------------
def _get_sqlite():
    global _sqlite_conn
    if _sqlite_conn is None:
        import sqlite3
        from pathlib import Path
        path = _sqlite_path_override or os.getenv("DATABASE_PATH", "longlist.db")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        _sqlite_conn = sqlite3.connect(str(path), check_same_thread=False)
        _sqlite_conn.row_factory = sqlite3.Row
    return _sqlite_conn


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------
_PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id       TEXT PRIMARY KEY,
    status       TEXT NOT NULL DEFAULT 'parsing',
    sender       TEXT NOT NULL DEFAULT '',
    subject      TEXT NOT NULL DEFAULT '',
    service_type TEXT NOT NULL DEFAULT '',
    package      TEXT NOT NULL DEFAULT '',
    thread_id    TEXT NOT NULL DEFAULT '',
    message_id   TEXT NOT NULL DEFAULT '',
    total_companies INTEGER NOT NULL DEFAULT 0,
    parsed       JSONB NOT NULL DEFAULT '{}',
    preview      JSONB NOT NULL DEFAULT '{}',
    payment_urls JSONB NOT NULL DEFAULT '{}',
    pipeline_result JSONB NOT NULL DEFAULT '{}',
    enriched_data JSONB NOT NULL DEFAULT '[]',
    error        TEXT NOT NULL DEFAULT '',
    extra        JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS stripe_sessions (
    session_id TEXT PRIMARY KEY,
    job_id     TEXT REFERENCES jobs(job_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_jobs_sender ON jobs(sender);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at DESC);
"""

_SQLITE_SCHEMA = """
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

# Known top-level columns in PG schema (for splitting data into columns vs extra)
_PG_COLUMNS = {
    "status", "sender", "subject", "service_type", "package",
    "thread_id", "message_id", "total_companies",
    "parsed", "preview", "payment_urls", "pipeline_result",
    "enriched_data", "error",
}


def init_db(db_path: str | None = None) -> None:
    global _sqlite_conn, _sqlite_path_override, _USE_PG
    if db_path:
        _sqlite_path_override = db_path
        _USE_PG = False
    # Close existing connections
    if _sqlite_conn is not None:
        _sqlite_conn.close()
        _sqlite_conn = None

    with _lock:
        if _USE_PG:
            _pg_exec(_PG_SCHEMA)
            logger.info("Job store initialized (PostgreSQL)")
        else:
            conn = _get_sqlite()
            conn.executescript(_SQLITE_SCHEMA)
            conn.commit()
            path = _sqlite_path_override or os.getenv("DATABASE_PATH", "longlist.db")
            logger.info("Job store initialized (SQLite: %s)", path)


# ---------------------------------------------------------------------------
# Unified job operations
# ---------------------------------------------------------------------------
def _split_data(data: dict) -> tuple[dict, dict]:
    """Split data dict into (columns, extra) for PG storage."""
    columns = {}
    extra = {}
    for k, v in data.items():
        if k == "job_id":
            continue
        if k in _PG_COLUMNS:
            columns[k] = v
        else:
            extra[k] = v
    return columns, extra


def get_job(job_id: str) -> dict[str, Any] | None:
    with _lock:
        if _USE_PG:
            row = _pg_exec(
                "SELECT * FROM jobs WHERE job_id = %s", (job_id,), fetch="one"
            )
            if not row:
                return None
            # Map tuple to dict using column names
            cols = [
                "job_id", "status", "sender", "subject", "service_type",
                "package", "thread_id", "message_id", "total_companies",
                "parsed", "preview", "payment_urls", "pipeline_result",
                "enriched_data", "error", "extra", "created_at", "updated_at",
            ]
            d = dict(zip(cols, row))
            # Merge extra back into top-level
            extra = d.pop("extra", {}) or {}
            if isinstance(extra, str):
                extra = json.loads(extra)
            # Ensure JSONB fields are dicts
            for k in ("parsed", "preview", "payment_urls", "pipeline_result"):
                if isinstance(d[k], str):
                    d[k] = json.loads(d[k])
            if isinstance(d.get("enriched_data"), str):
                d["enriched_data"] = json.loads(d["enriched_data"])
            d.update(extra)
            # Convert datetimes to strings
            for k in ("created_at", "updated_at"):
                if d.get(k) and hasattr(d[k], "isoformat"):
                    d[k] = d[k].isoformat()
            return d
        else:
            row = _get_sqlite().execute(
                "SELECT data FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            if not row:
                return None
            return json.loads(row["data"])


def put_job(job_id: str, data: dict[str, Any]) -> None:
    data = dict(data)
    data.setdefault("job_id", job_id)
    now = _now()

    with _lock:
        if _USE_PG:
            columns, extra = _split_data(data)
            _pg_exec("""
                INSERT INTO jobs (job_id, status, sender, subject, service_type,
                    package, thread_id, message_id, total_companies,
                    parsed, preview, payment_urls, pipeline_result,
                    enriched_data, error, extra, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (job_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    sender = EXCLUDED.sender,
                    subject = EXCLUDED.subject,
                    service_type = EXCLUDED.service_type,
                    package = EXCLUDED.package,
                    thread_id = EXCLUDED.thread_id,
                    message_id = EXCLUDED.message_id,
                    total_companies = EXCLUDED.total_companies,
                    parsed = EXCLUDED.parsed,
                    preview = EXCLUDED.preview,
                    payment_urls = EXCLUDED.payment_urls,
                    pipeline_result = EXCLUDED.pipeline_result,
                    enriched_data = EXCLUDED.enriched_data,
                    error = EXCLUDED.error,
                    extra = EXCLUDED.extra,
                    updated_at = NOW()
            """, (
                job_id,
                columns.get("status", ""),
                columns.get("sender", ""),
                columns.get("subject", ""),
                columns.get("service_type", ""),
                columns.get("package", ""),
                columns.get("thread_id", ""),
                columns.get("message_id", ""),
                int(columns.get("total_companies", 0) or 0),
                json.dumps(columns.get("parsed", {}), default=str),
                json.dumps(columns.get("preview", {}), default=str),
                json.dumps(columns.get("payment_urls", {}), default=str),
                json.dumps(columns.get("pipeline_result", {}), default=str),
                json.dumps(columns.get("enriched_data", []), default=str),
                columns.get("error", ""),
                json.dumps(extra, default=str),
            ))
        else:
            payload = json.dumps(data, default=str)
            _get_sqlite().execute("""
                INSERT INTO jobs (job_id, data, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
            """, (job_id, payload, now))
            _get_sqlite().commit()


def merge_job(job_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    current = get_job(job_id) or {}
    current.update(patch)
    put_job(job_id, current)
    return current


def list_job_ids() -> list[str]:
    with _lock:
        if _USE_PG:
            rows = _pg_exec(
                "SELECT job_id FROM jobs ORDER BY updated_at DESC",
                fetch="all",
            )
            return [r[0] for r in (rows or [])]
        else:
            rows = _get_sqlite().execute(
                "SELECT job_id FROM jobs ORDER BY updated_at DESC"
            ).fetchall()
            return [r["job_id"] for r in rows]


def list_jobs_summary() -> dict[str, dict[str, Any]]:
    with _lock:
        if _USE_PG:
            rows = _pg_exec(
                "SELECT job_id, status, sender, total_companies, package, "
                "service_type, created_at FROM jobs ORDER BY created_at DESC",
                fetch="all",
            )
            out = {}
            for r in (rows or []):
                out[r[0]] = {
                    "status": r[1], "sender": r[2], "total": r[3],
                    "package": r[4], "service_type": r[5],
                    "created_at": r[6].isoformat() if hasattr(r[6], "isoformat") else r[6],
                }
            return out
        else:
            out = {}
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
        if _USE_PG:
            row = _pg_exec("SELECT COUNT(*) FROM jobs", fetch="one")
            return row[0] if row else 0
        else:
            row = _get_sqlite().execute("SELECT COUNT(*) AS c FROM jobs").fetchone()
            return int(row["c"]) if row else 0


def try_claim_stripe_session(session_id: str, job_id: str) -> bool:
    if not session_id:
        logger.error("try_claim_stripe_session: empty session_id")
        return False
    with _lock:
        if _USE_PG:
            try:
                _pg_exec(
                    "INSERT INTO stripe_sessions (session_id, job_id) VALUES (%s, %s)",
                    (session_id, job_id or ""),
                )
                return True
            except Exception:
                logger.info("Duplicate Stripe webhook ignored for session %s", session_id)
                return False
        else:
            import sqlite3
            try:
                _get_sqlite().execute(
                    "INSERT INTO stripe_sessions (session_id, job_id, created_at) VALUES (?, ?, ?)",
                    (session_id, job_id or "", _now()),
                )
                _get_sqlite().commit()
                return True
            except sqlite3.IntegrityError:
                _get_sqlite().rollback()
                logger.info("Duplicate Stripe webhook ignored for session %s", session_id)
                return False


def find_job_by_thread(thread_id: str) -> dict[str, Any] | None:
    """Find the most recent job for a given AgentMail thread_id."""
    if not thread_id:
        return None
    # Get job_id inside lock, then call get_job outside to avoid deadlock
    # (_lock is not reentrant, and get_job also acquires _lock)
    job_id_found: str | None = None
    with _lock:
        if _USE_PG:
            row = _pg_exec(
                "SELECT job_id FROM jobs WHERE thread_id = %s ORDER BY created_at DESC LIMIT 1",
                (thread_id,), fetch="one",
            )
            if row:
                job_id_found = row[0]
        else:
            rows = _get_sqlite().execute(
                "SELECT job_id, data FROM jobs ORDER BY updated_at DESC"
            ).fetchall()
            for r in rows:
                data = json.loads(r["data"])
                if data.get("thread_id") == thread_id:
                    return data  # SQLite path returns data directly (no nested lock)
    # PG path: call get_job outside the lock
    if job_id_found:
        return get_job(job_id_found)
    return None
