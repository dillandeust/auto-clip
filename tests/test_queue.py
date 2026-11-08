import pytest
from autoclip.db import connect
from autoclip import queue

@pytest.fixture
def conn():
    c = connect(":memory:")
    queue.init_db(c)
    yield c
    c.close()

def _enq(conn, scheduled_at=None, platform="tiktok"):
    return queue.enqueue(
        conn, job_id="job1", clip_index=0, clip_path="/tmp/clip0.mp4",
        platform=platform, caption="hello", scheduled_at=scheduled_at,
        now="2026-11-08T10:00:00Z",
    )

def test_enqueue_returns_id_and_is_pending(conn):
    rid = _enq(conn)
    row = queue.get(conn, rid)
    assert row["status"] == "pending"
    assert row["platform"] == "tiktok"
    assert row["attempts"] == 0

def test_due_respects_schedule(conn):
    now_due = _enq(conn, scheduled_at="2026-11-08T09:00:00Z")
    later = _enq(conn, scheduled_at="2026-11-08T23:00:00Z")
    asap = _enq(conn, scheduled_at=None)
    due_ids = {r["id"] for r in queue.due(conn, now="2026-11-08T10:00:00Z")}
    assert now_due in due_ids
    assert asap in due_ids
    assert later not in due_ids

def test_mark_posted(conn):
    rid = _enq(conn)
    queue.mark_in_progress(conn, rid, now="2026-11-08T10:00:01Z")
    queue.mark_posted(conn, rid, url="https://tiktok.com/x", now="2026-11-08T10:00:05Z")
    row = queue.get(conn, rid)
    assert row["status"] == "posted"
    assert row["posted_url"] == "https://tiktok.com/x"

def test_failure_retries_then_needs_manual(conn):
    rid = _enq(conn)
    queue.mark_failed(conn, rid, error="boom", max_attempts=3, now="2026-11-08T10:00:02Z")
    assert queue.get(conn, rid)["status"] == "pending"
    assert queue.get(conn, rid)["attempts"] == 1
    queue.mark_failed(conn, rid, error="boom", max_attempts=3, now="2026-11-08T10:00:03Z")
    assert queue.get(conn, rid)["status"] == "pending"
    queue.mark_failed(conn, rid, error="boom", max_attempts=3, now="2026-11-08T10:00:04Z")
    row = queue.get(conn, rid)
    assert row["status"] == "needs_manual"
    assert row["attempts"] == 3
    assert row["last_error"] == "boom"

def test_mark_needs_manual_directly(conn):
    rid = _enq(conn)
    queue.mark_needs_manual(conn, rid, error="login wall", now="2026-11-08T10:00:02Z")
    assert queue.get(conn, rid)["status"] == "needs_manual"

def test_list_by_status(conn):
    a = _enq(conn)
    b = _enq(conn, platform="youtube")
    queue.mark_needs_manual(conn, b, error="x", now="2026-11-08T10:00:02Z")
    manual = queue.list_by_status(conn, "needs_manual")
    assert [r["id"] for r in manual] == [b]
