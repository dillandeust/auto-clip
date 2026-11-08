from __future__ import annotations
from typing import List, Optional
from . import queue

def enqueue_clip(conn, *, job_id: str, clip_index: int, clip_path: str,
                 platforms: List[str], caption: str,
                 scheduled_at: Optional[str], now: str,
                 profile: str = "default") -> List[int]:
    ids = []
    for platform in platforms:
        ids.append(queue.enqueue(
            conn, job_id=job_id, clip_index=clip_index, clip_path=clip_path,
            platform=platform, caption=caption, scheduled_at=scheduled_at,
            now=now, profile=profile,
        ))
    return ids
