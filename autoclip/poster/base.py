from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

@dataclass
class PostResult:
    ok: bool
    url: Optional[str] = None
    error: Optional[str] = None
    screenshot: Optional[str] = None

class LoginRequired(Exception):
    """Levée quand la session navigateur n'est plus connectée."""

class Poster(Protocol):
    name: str
    def post(self, clip_path: str, caption: str, *,
             profile: str = "default", dry_run: bool = False) -> PostResult: ...

def session_dir(platform: str, profile: str, *, profiles_root: str = "profiles") -> Path:
    d = Path(profiles_root) / platform / profile
    d.mkdir(parents=True, exist_ok=True)
    return d

def screenshot_path(platform: str, label: str, *, logs_root: str = "logs") -> str:
    Path(logs_root).mkdir(parents=True, exist_ok=True)
    return str(Path(logs_root) / f"{platform}_{label}.png")
