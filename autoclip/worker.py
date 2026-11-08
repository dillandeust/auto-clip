from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Dict

from . import queue
from .db import connect
from .config import load
from .poster.base import Poster, PostResult, LoginRequired

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def run_once(conn, posters: Dict[str, Poster], *, now: str, max_attempts: int) -> int:
    """Traite tous les posts dus. Retourne le nombre traité."""
    rows = queue.due(conn, now=now)
    for row in rows:
        rid = row["id"]
        platform = row["platform"]
        queue.mark_in_progress(conn, rid, now=now)
        poster = posters.get(platform)
        if poster is None:
            queue.mark_needs_manual(
                conn, rid, error=f"aucun adaptateur pour '{platform}'", now=now)
            continue
        try:
            result: PostResult = poster.post(
                row["clip_path"], row["caption"], profile=row["profile"])
            if result.ok:
                queue.mark_posted(conn, rid, url=result.url or "", now=now)
            else:
                queue.mark_failed(conn, rid, error=result.error or "échec",
                                  max_attempts=max_attempts, now=now)
        except LoginRequired as e:
            queue.mark_needs_manual(conn, rid, error=f"login requis: {e}", now=now)
        except Exception as e:  # garde-fou : tout autre échec -> retry/needs_manual
            queue.mark_failed(conn, rid, error=str(e),
                              max_attempts=max_attempts, now=now)
    return len(rows)

def run_forever(poll_seconds: int = 15) -> None:
    from .poster.tiktok import TikTokPoster
    from .poster.instagram import InstagramPoster
    from .poster.youtube import YouTubePoster
    cfg = load()
    conn = connect(cfg.db_path)
    queue.init_db(conn)
    posters = {
        "tiktok": TikTokPoster(cfg),
        "instagram": InstagramPoster(cfg),
        "youtube": YouTubePoster(cfg),
    }
    print(f"[autoclip] worker démarré (poll={poll_seconds}s, db={cfg.db_path})")
    while True:
        n = run_once(conn, posters, now=_now(), max_attempts=cfg.max_attempts)
        if n:
            print(f"[autoclip] {n} post(s) traité(s)")
        time.sleep(poll_seconds)
