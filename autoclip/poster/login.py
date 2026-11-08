from __future__ import annotations
from playwright.sync_api import sync_playwright
from .base import session_dir
from ..config import Config

LOGIN_URLS = {
    "tiktok": "https://www.tiktok.com/login",
    "instagram": "https://www.instagram.com/accounts/login/",
    "youtube": "https://accounts.google.com/ServiceLogin?service=youtube",
}

def login(platform: str, cfg: Config, profile: str = "default") -> None:
    if platform not in LOGIN_URLS:
        raise SystemExit(f"plateforme inconnue: {platform}")
    udd = session_dir(platform, profile, profiles_root=cfg.profiles_dir)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(str(udd), headless=False)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(LOGIN_URLS[platform])
        print(f"\n[autoclip] Connecte-toi à {platform} dans la fenêtre, "
              f"puis reviens ici et appuie sur Entrée pour sauvegarder la session.")
        input()
        ctx.close()  # la session persiste dans user_data_dir
    print(f"[autoclip] session {platform}/{profile} enregistrée dans {udd}")
