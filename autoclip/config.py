from __future__ import annotations
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _bool(name: str, default: bool) -> bool:
    return (os.environ.get(name) or str(default)).strip().lower() in ("1", "true", "yes", "on")

@dataclass(frozen=True)
class Config:
    db_path: str
    profiles_dir: str
    logs_dir: str
    headless: bool
    max_attempts: int

def load() -> Config:
    return Config(
        db_path=os.environ.get("AUTOCLIP_DB", "autoclip.db"),
        profiles_dir=os.environ.get("PROFILES_DIR", "profiles"),
        logs_dir=os.environ.get("LOGS_DIR", "logs"),
        headless=_bool("AUTOCLIP_HEADLESS", False),
        max_attempts=int(os.environ.get("AUTOCLIP_MAX_ATTEMPTS", "3")),
    )
