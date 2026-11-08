from __future__ import annotations
import sqlite3
from typing import Optional

PENDING = "pending"
IN_PROGRESS = "in_progress"
POSTED = "posted"
FAILED = "failed"
NEEDS_MANUAL = "needs_manual"

def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS post_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            clip_index INTEGER NOT NULL,
            clip_path TEXT NOT NULL,
            platform TEXT NOT NULL,
            profile TEXT NOT NULL DEFAULT 'default',
            caption TEXT NOT NULL DEFAULT '',
            scheduled_at TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            posted_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

def enqueue(conn, *, job_id, clip_index, clip_path, platform, caption,
            scheduled_at: Optional[str], now: str, profile: str = "default") -> int:
    cur = conn.execute(
        """INSERT INTO post_queue
           (job_id, clip_index, clip_path, platform, profile, caption,
            scheduled_at, status, attempts, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,0,?,?)""",
        (job_id, clip_index, clip_path, platform, profile, caption,
         scheduled_at, PENDING, now, now),
    )
    return int(cur.lastrowid)

def get(conn, rid: int):
    return conn.execute("SELECT * FROM post_queue WHERE id=?", (rid,)).fetchone()

def due(conn, *, now: str):
    return conn.execute(
        """SELECT * FROM post_queue
           WHERE status=? AND (scheduled_at IS NULL OR scheduled_at <= ?)
           ORDER BY id ASC""",
        (PENDING, now),
    ).fetchall()

def list_by_status(conn, status: str):
    return conn.execute(
        "SELECT * FROM post_queue WHERE status=? ORDER BY id ASC", (status,)
    ).fetchall()

def mark_in_progress(conn, rid: int, *, now: str) -> None:
    conn.execute(
        "UPDATE post_queue SET status=?, updated_at=? WHERE id=?",
        (IN_PROGRESS, now, rid),
    )

def mark_posted(conn, rid: int, *, url: str, now: str) -> None:
    conn.execute(
        "UPDATE post_queue SET status=?, posted_url=?, updated_at=? WHERE id=?",
        (POSTED, url, now, rid),
    )

def mark_failed(conn, rid: int, *, error: str, max_attempts: int, now: str) -> None:
    row = get(conn, rid)
    attempts = (row["attempts"] or 0) + 1
    status = NEEDS_MANUAL if attempts >= max_attempts else PENDING
    conn.execute(
        "UPDATE post_queue SET status=?, attempts=?, last_error=?, updated_at=? WHERE id=?",
        (status, attempts, error, now, rid),
    )

def mark_needs_manual(conn, rid: int, *, error: str, now: str) -> None:
    conn.execute(
        "UPDATE post_queue SET status=?, last_error=?, updated_at=? WHERE id=?",
        (NEEDS_MANUAL, error, now, rid),
    )

def cancel(conn, rid: int) -> None:
    conn.execute("DELETE FROM post_queue WHERE id=? AND status=?", (rid, PENDING))
