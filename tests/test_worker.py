import pytest
from autoclip.db import connect
from autoclip import queue, worker
from autoclip.poster.base import PostResult, LoginRequired

@pytest.fixture
def conn():
    c = connect(":memory:")
    queue.init_db(c)
    yield c
    c.close()

class FakePoster:
    def __init__(self, name, behavior):
        self.name = name
        self.behavior = behavior  # "ok" | "fail" | "login"
        self.calls = 0
    def post(self, clip_path, caption, *, profile="default", dry_run=False):
        self.calls += 1
        if self.behavior == "ok":
            return PostResult(ok=True, url=f"https://{self.name}/x")
        if self.behavior == "login":
            raise LoginRequired("not logged in")
        return PostResult(ok=False, error="boom")

def _enq(conn, platform):
    return queue.enqueue(conn, job_id="j", clip_index=0, clip_path="/tmp/c.mp4",
                         platform=platform, caption="cap", scheduled_at=None,
                         now="2026-11-08T10:00:00Z")

def test_run_once_posts_due_ok(conn):
    rid = _enq(conn, "tiktok")
    posters = {"tiktok": FakePoster("tiktok", "ok")}
    worker.run_once(conn, posters, now="2026-11-08T10:00:00Z", max_attempts=3)
    row = queue.get(conn, rid)
    assert row["status"] == "posted"
    assert row["posted_url"] == "https://tiktok/x"

def test_run_once_failure_increments_attempts(conn):
    rid = _enq(conn, "tiktok")
    posters = {"tiktok": FakePoster("tiktok", "fail")}
    worker.run_once(conn, posters, now="2026-11-08T10:00:00Z", max_attempts=3)
    row = queue.get(conn, rid)
    assert row["status"] == "pending"
    assert row["attempts"] == 1

def test_run_once_login_required_goes_manual(conn):
    rid = _enq(conn, "tiktok")
    posters = {"tiktok": FakePoster("tiktok", "login")}
    worker.run_once(conn, posters, now="2026-11-08T10:00:00Z", max_attempts=3)
    assert queue.get(conn, rid)["status"] == "needs_manual"

def test_run_once_unknown_platform_goes_manual(conn):
    rid = _enq(conn, "snapchat")
    worker.run_once(conn, {}, now="2026-11-08T10:00:00Z", max_attempts=3)
    row = queue.get(conn, rid)
    assert row["status"] == "needs_manual"
    assert "snapchat" in (row["last_error"] or "")

def test_run_once_ignores_not_due(conn):
    rid = queue.enqueue(conn, job_id="j", clip_index=0, clip_path="/tmp/c.mp4",
                        platform="tiktok", caption="cap",
                        scheduled_at="2026-11-08T23:00:00Z", now="2026-11-08T10:00:00Z")
    posters = {"tiktok": FakePoster("tiktok", "ok")}
    worker.run_once(conn, posters, now="2026-11-08T10:00:00Z", max_attempts=3)
    assert queue.get(conn, rid)["status"] == "pending"
