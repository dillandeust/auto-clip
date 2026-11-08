import pytest
from autoclip.db import connect
from autoclip import queue
from autoclip.enqueue_api import enqueue_clip

@pytest.fixture
def conn():
    c = connect(":memory:")
    queue.init_db(c)
    yield c
    c.close()

def test_enqueue_one_row_per_platform(conn):
    ids = enqueue_clip(
        conn,
        job_id="job1", clip_index=2, clip_path="/out/job1/clip_2.mp4",
        platforms=["tiktok", "youtube"],
        caption="Grosse punchline #fyp",
        scheduled_at="2026-11-09T08:00:00Z",
        now="2026-11-08T10:00:00Z",
    )
    assert len(ids) == 2
    rows = conn.execute("SELECT platform, caption, scheduled_at FROM post_queue ORDER BY id").fetchall()
    assert [r["platform"] for r in rows] == ["tiktok", "youtube"]
    assert rows[0]["scheduled_at"] == "2026-11-09T08:00:00Z"
    assert rows[0]["caption"] == "Grosse punchline #fyp"
