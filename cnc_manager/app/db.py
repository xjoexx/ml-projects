from __future__ import annotations

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "cnc_manager.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS programs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT UNIQUE NOT NULL,
              code_text TEXT NOT NULL,
              estimated_duration_seconds INTEGER,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS jobs (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              program_id INTEGER NOT NULL,
              status TEXT NOT NULL,
              priority INTEGER NOT NULL,
              queued_at TEXT NOT NULL,
              started_at TEXT,
              finished_at TEXT,
              machine_name TEXT,
              error_message TEXT,
              FOREIGN KEY(program_id) REFERENCES programs(id)
            );
            """
        )
        conn.commit()


# Program operations

def list_programs() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, name, code_text, estimated_duration_seconds, created_at, updated_at FROM programs ORDER BY created_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def create_program(name: str, code_text: str, estimated_duration_seconds: Optional[int]) -> int:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO programs(name, code_text, estimated_duration_seconds, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, code_text, estimated_duration_seconds, now, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_program(program_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, name, code_text, estimated_duration_seconds, created_at, updated_at FROM programs WHERE id = ?",
            (program_id,),
        ).fetchone()
        return dict(row) if row else None


def find_program_by_name(name: str) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, name FROM programs WHERE name = ?",
            (name,),
        ).fetchone()
        return dict(row) if row else None


# Job operations

def list_jobs() -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT j.*, p.name AS program_name
            FROM jobs j
            JOIN programs p ON p.id = j.program_id
            ORDER BY j.status, j.priority, j.queued_at
            """
        ).fetchall()
        return [dict(r) for r in rows]


def enqueue_job(program_id: int, priority: int = 100) -> int:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO jobs(program_id, status, priority, queued_at)
            VALUES (?, 'queued', ?, ?)
            """,
            (program_id, priority, now),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_job(job_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None


def update_job_status(job_id: int, status: str, *, machine_name: Optional[str] = None, error_message: Optional[str] = None) -> None:
    now = datetime.utcnow().isoformat()
    with _connect() as conn:
        if status == "running":
            conn.execute(
                "UPDATE jobs SET status = ?, started_at = ?, machine_name = ?, error_message = NULL WHERE id = ?",
                (status, now, machine_name, job_id),
            )
        elif status in ("completed", "failed", "canceled"):
            conn.execute(
                "UPDATE jobs SET status = ?, finished_at = ?, error_message = COALESCE(?, error_message) WHERE id = ?",
                (status, now, error_message, job_id),
            )
        else:
            conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
        conn.commit()


def get_next_queued_job() -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT j.*, p.name AS program_name, p.code_text, p.estimated_duration_seconds
            FROM jobs j
            JOIN programs p ON p.id = j.program_id
            WHERE j.status = 'queued'
            ORDER BY j.priority ASC, j.queued_at ASC, j.id ASC
            LIMIT 1
            """
        ).fetchone()
        return dict(row) if row else None


def get_job_status(job_id: int) -> Optional[str]:
    with _connect() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return row[0] if row else None


# Reports

def summary_counts_and_avg() -> Dict[str, Any]:
    with _connect() as conn:
        counts_rows = conn.execute(
            "SELECT status, COUNT(id) FROM jobs GROUP BY status"
        ).fetchall()
        avg_row = conn.execute(
            """
            SELECT AVG(strftime('%s', finished_at) - strftime('%s', started_at))
            FROM jobs WHERE finished_at IS NOT NULL AND started_at IS NOT NULL
            """
        ).fetchone()
        return {
            "by_status": {r[0]: r[1] for r in counts_rows},
            "avg_duration_seconds": float(avg_row[0]) if avg_row and avg_row[0] is not None else None,
        }


def recent_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT j.*, p.name AS program_name
            FROM jobs j
            JOIN programs p ON p.id = j.program_id
            ORDER BY j.queued_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]